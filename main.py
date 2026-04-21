import threading
import queue
import sys
import os
import re
import time
import traceback
import winsound

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QCoreApplication

from actions import perform_action
from screen_analysis import analyze_screen, is_screen_request
from gui import KoraDashboard
from brain import KoraBrain
from tasks import ReminderManager, check_for_tasks
from voice import speak
from ears import extract_wake_command, listen, calibrate_microphone
from mode_select import ask_mode

# Set by the startup dialog — "voice", "text", or "both"
INPUT_MODE = "both"   # overwritten at launch

# ── Core objects ──────────────────────────────────────────────────────────────
brain            = KoraBrain()
reminder_manager = ReminderManager()

# Shared queue — both voice thread and text input feed into this.
# Each item is a dict: {"text": str, "source": "voice" | "text"}
command_queue = queue.Queue()

# ── Flags / locks ─────────────────────────────────────────────────────────────
sleep_mode          = threading.Event()
wake_notice_pending = threading.Event()
active_alert_ids    = set()
active_alerts_lock  = threading.Lock()
kora_busy           = threading.Event()   # set while Kora is processing/speaking

# ── Config ────────────────────────────────────────────────────────────────────
ENABLE_WAKE_WORD = os.getenv("KORA_ENABLE_WAKE_WORD", "0").lower() in {"1", "true", "yes", "on"}
WAKE_STATUS              = "LISTENING FOR WAKE WORD"
COMMAND_STATUS           = "LISTENING FOR COMMAND"
DEFAULT_LISTENING_STATUS = WAKE_STATUS if ENABLE_WAKE_WORD else "LISTENING..."
SLEEPING_STATUS          = "SLEEPING..."
ALERT_REPEAT_INTERVAL    = 10
MAX_ALERT_REPEATS        = 6

# ── Command sets ──────────────────────────────────────────────────────────────
SHUTDOWN_COMMANDS = {
    "shutdown", "power down", "exit", "exit kora",
    "quit kora", "shutdown kora", "close kora",
}
RESET_COMMANDS = {
    "forget everything", "reset conversation", "clear memory",
    "start fresh", "wipe memory", "clear conversation",
}
RECALIBRATE_COMMANDS = {
    "recalibrate", "recalibrate mic", "calibrate microphone",
    "calibrate mic", "fix microphone", "reset microphone",
}
SLEEP_COMMANDS = {
    "go to sleep", "sleep mode", "go silent", "be quiet",
    "stay quiet", "stop talking", "don't talk", "dont talk",
    "do not talk", "stop listening", "mute yourself",
}
DISMISS_ALERT_COMMANDS = {
    "dismiss reminder", "stop reminder", "stop the reminder",
    "dismiss the reminder", "dismiss timer", "stop timer",
    "stop the timer", "dismiss alert", "stop alert",
    "got it", "okay thanks", "okay thank you",
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def normalize_voice_command(cmd):
    n = re.sub(r"[^a-z0-9'\s]+", " ", str(cmd).lower())
    n = re.sub(r"\b(kora|please)\b", " ", n)
    return " ".join(n.split())


def command_matches(normalized, phrases):
    for phrase in phrases:
        if normalized == phrase or f" {phrase} " in f" {normalized} ":
            return True
    return False


def is_sleep_request(cmd):
    return command_matches(normalize_voice_command(cmd), SLEEP_COMMANDS)


def is_dismiss_alert_request(cmd):
    return command_matches(normalize_voice_command(cmd), DISMISS_ALERT_COMMANDS)


def register_active_alert(item_id):
    with active_alerts_lock:
        active_alert_ids.add(item_id)


def clear_active_alert(item_id):
    with active_alerts_lock:
        active_alert_ids.discard(item_id)


def is_alert_active(item_id):
    with active_alerts_lock:
        return item_id in active_alert_ids


def dismiss_all_alerts():
    with active_alerts_lock:
        count = len(active_alert_ids)
        active_alert_ids.clear()
        return count


# ── Voice listener thread ─────────────────────────────────────────────────────

def voice_listener_loop(ui):
    """
    Runs forever in a background thread.
    Listens for voice commands and puts them into command_queue.
    Completely independent of the text input path.
    """
    while True:
        try:
            if sleep_mode.is_set():
                ui.status_signal.emit(SLEEPING_STATUS)
                heard = listen()
                if not heard:
                    continue
                wake_cmd = extract_wake_command(heard)
                if wake_cmd is None:
                    continue
                sleep_mode.clear()
                wake_notice_pending.set()
                if wake_cmd:
                    command_queue.put({"text": wake_cmd, "source": "voice"})
                continue

            if not ENABLE_WAKE_WORD:
                ui.status_signal.emit(DEFAULT_LISTENING_STATUS)
                heard = listen()
                if heard:
                    command_queue.put({"text": heard, "source": "voice"})
                continue

            # Wake-word mode
            ui.status_signal.emit(DEFAULT_LISTENING_STATUS)
            heard = listen()
            if not heard:
                continue
            wake_cmd = extract_wake_command(heard)
            if wake_cmd is None:
                continue
            if wake_cmd:
                command_queue.put({"text": wake_cmd, "source": "voice"})
            else:
                ui.log_signal.emit("SYSTEM", "Wake word detected.")
                ui.status_signal.emit(COMMAND_STATUS)
                speak("Yes?")
                follow_up = listen()
                if follow_up:
                    command_queue.put({"text": follow_up, "source": "voice"})

        except Exception:
            print(f"[Voice listener error]: {traceback.format_exc()}")
            time.sleep(1)


# ── Text input handler (called from Qt signal) ────────────────────────────────

def on_text_submitted(text: str):
    """
    Called on the Qt thread when the user submits a typed message.
    Just drops it into the shared queue — the logic thread picks it up.
    """
    if text.strip():
        command_queue.put({"text": text.strip(), "source": "text"})


# ── Reminder loop ─────────────────────────────────────────────────────────────

def reminder_loop(ui):
    while True:
        try:
            due_items = reminder_manager.pop_due()
            for item in due_items:
                threading.Thread(
                    target=deliver_reminder_alert, args=(ui, item), daemon=True
                ).start()
        except Exception:
            print(f"Reminder loop error: {traceback.format_exc()}")
        time.sleep(1)


def play_alert_tone():
    try:
        winsound.Beep(1200, 350)
        winsound.Beep(1000, 350)
    except Exception:
        winsound.MessageBeep()


def deliver_reminder_alert(ui, item):
    base_message = item.trigger_message()
    was_sleeping = sleep_mode.is_set()
    register_active_alert(item.id)
    try:
        for index in range(MAX_ALERT_REPEATS):
            if not is_alert_active(item.id):
                break
            if index == 0:
                message = base_message
            elif index == MAX_ALERT_REPEATS - 1:
                message = f"Final reminder: {base_message}"
            else:
                message = f"Follow-up reminder: {base_message}"
            ui.log_signal.emit("REMINDER", message)
            ui.status_signal.emit("SPEAKING...")
            play_alert_tone()
            speak(message)
            ui.status_signal.emit(SLEEPING_STATUS if sleep_mode.is_set() else DEFAULT_LISTENING_STATUS)
            if index < MAX_ALERT_REPEATS - 1 and is_alert_active(item.id):
                time.sleep(ALERT_REPEAT_INTERVAL)
    finally:
        clear_active_alert(item.id)


# ── Main logic loop ───────────────────────────────────────────────────────────

def kora_logic(ui):
    """
    Single loop that processes commands from the shared queue.
    Commands arrive from EITHER the voice thread OR the text input — 
    this loop doesn't care which, it handles both identically.
    """
    ui.status_signal.emit("SYSTEM ONLINE")
    ui.log_signal.emit("SYSTEM", f"Kora initialized — mode: {INPUT_MODE.upper()}")

    # Only calibrate mic if voice input is active
    if INPUT_MODE in ("voice", "both"):
        ui.status_signal.emit("CALIBRATING MIC...")
        ui.log_signal.emit("SYSTEM", "Calibrating microphone — stay silent for 2 seconds...")
        calibrate_microphone(duration=2.0)
        ui.log_signal.emit("SYSTEM", "Microphone calibrated.")

    mode_msg = {
        "voice": "Voice mode active. Just speak.",
        "text":  "Text mode active. Type below and press Enter.",
        "both":  "Voice and text active. Speak or type — both work.",
    }.get(INPUT_MODE, "Systems online.")
    speak(mode_msg) if INPUT_MODE in ("voice", "both") else None
    ui.log_signal.emit("SYSTEM", mode_msg)
    ui.status_signal.emit(DEFAULT_LISTENING_STATUS if INPUT_MODE != "text" else "TEXT MODE")

    # Handle wake transition once voice loop wakes from sleep
    def handle_wake_transition():
        if not wake_notice_pending.is_set():
            return
        wake_notice_pending.clear()
        ui.log_signal.emit("SYSTEM", "Kora is awake.")
        ui.status_signal.emit("SPEAKING...")
        speak("I'm awake.")
        ui.status_signal.emit(DEFAULT_LISTENING_STATUS)

    while True:
        try:
            # Block until a command arrives (from voice or text)
            item = command_queue.get(timeout=0.2)
        except queue.Empty:
            handle_wake_transition()
            continue

        handle_wake_transition()

        query  = item["text"].strip()
        source = item["source"]   # "voice" or "text"

        if not query:
            continue

        # Show in log with source hint
        source_tag = "🎙" if source == "voice" else "⌨"
        ui.log_signal.emit("USER", f"{source_tag} {query}")
        ui.status_signal.emit("PROCESSING...")
        kora_busy.set()

        cmd = query.lower()

        try:
            # ── Shutdown ──────────────────────────────────────────────────────
            if cmd.strip() in SHUTDOWN_COMMANDS:
                ui.log_signal.emit("SYSTEM", "Shutting down. Goodbye.")
                speak("Goodbye.")
                QCoreApplication.quit()
                os._exit(0)

            norm_cmd = normalize_voice_command(cmd)

            # ── Recalibrate ───────────────────────────────────────────────────
            if command_matches(norm_cmd, RECALIBRATE_COMMANDS):
                r = "Recalibrating microphone. Please stay silent for 2 seconds."
                ui.log_signal.emit("KORA", r)
                speak(r)
                ui.status_signal.emit("CALIBRATING MIC...")
                calibrate_microphone(duration=2.0)
                done = "Microphone recalibrated."
                ui.log_signal.emit("SYSTEM", done)
                speak(done)
                ui.status_signal.emit(DEFAULT_LISTENING_STATUS)
                ui.re_enable_input()
                kora_busy.clear()
                continue

            # ── Reset conversation ────────────────────────────────────────────
            if command_matches(norm_cmd, RESET_COMMANDS):
                brain.reset_conversation()
                r = "Conversation history cleared. Starting fresh."
                ui.log_signal.emit("KORA", r)
                speak(r)
                ui.status_signal.emit(DEFAULT_LISTENING_STATUS)
                ui.re_enable_input()
                kora_busy.clear()
                continue

            # ── Dismiss alert ─────────────────────────────────────────────────
            if is_dismiss_alert_request(cmd):
                dismissed = dismiss_all_alerts()
                r = (f"Stopped {dismissed} active alert{'s' if dismissed != 1 else ''}."
                     if dismissed else "No active alerts right now.")
                ui.log_signal.emit("KORA", r)
                speak(r)
                ui.status_signal.emit(DEFAULT_LISTENING_STATUS)
                ui.re_enable_input()
                kora_busy.clear()
                continue

            # ── Sleep ─────────────────────────────────────────────────────────
            if is_sleep_request(cmd):
                sleep_mode.set()
                r = "Going to sleep. Say Hey Kora to wake me."
                ui.log_signal.emit("KORA", r)
                speak(r)
                ui.status_signal.emit(SLEEPING_STATUS)
                ui.re_enable_input()
                kora_busy.clear()
                continue

            # ── Desktop actions ───────────────────────────────────────────────
            action_reply = perform_action(cmd)
            if action_reply:
                ui.log_signal.emit("KORA", action_reply)
                ui.status_signal.emit("SPEAKING...")
                speak(action_reply)
                ui.status_signal.emit(DEFAULT_LISTENING_STATUS)
                ui.re_enable_input()
                kora_busy.clear()
                continue

            # ── Screen analysis ───────────────────────────────────────────────
            if is_screen_request(cmd):
                screen_reply = analyze_screen(query)
                ui.log_signal.emit("KORA", screen_reply)
                speak(screen_reply)
                ui.status_signal.emit(DEFAULT_LISTENING_STATUS)
                ui.re_enable_input()
                kora_busy.clear()
                continue

            # ── Tasks / reminders ─────────────────────────────────────────────
            task = check_for_tasks(cmd, reminder_manager)
            if task:
                ui.log_signal.emit("KORA", task["reply"])
                speak(task["reply"])
                if task.get("action") == "schedule" and task.get("item"):
                    brain.learn(
                        f"{task['item'].kind.upper()} scheduled: "
                        f"{task['item'].task} at {task['item'].due_phrase()}"
                    )
                ui.status_signal.emit(DEFAULT_LISTENING_STATUS)
                ui.re_enable_input()
                kora_busy.clear()
                continue

            # ── General reply (LLM) ───────────────────────────────────────────
            brain.learn(query)
            res = brain.generate_reply(query)
            ui.log_signal.emit("KORA", res)
            ui.status_signal.emit("SPEAKING...")

            # Speak only for voice input or voice-capable modes
            if source == "voice" or INPUT_MODE == "voice":
                speak(res)

            ui.status_signal.emit(DEFAULT_LISTENING_STATUS)
            ui.re_enable_input()
            kora_busy.clear()

        except Exception as e:
            err = f"Error: {str(e)}"
            ui.log_signal.emit("SYSTEM ERROR", err)
            print(f"[Logic error]: {traceback.format_exc()}")
            ui.status_signal.emit("RECOVERED")
            ui.re_enable_input()
            kora_busy.clear()


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = QApplication(sys.argv)

    # ── Show mode selector before anything else ───────────────────────────────
    from mode_select import ask_mode
    INPUT_MODE = ask_mode()          # blocks until user picks, then returns

    hud = KoraDashboard(input_mode=INPUT_MODE)
    hud.show()

    # Connect text input signal to queue handler
    hud.text_input_signal.connect(on_text_submitted)

    # Only start voice listener if mode includes voice
    if INPUT_MODE in ("voice", "both"):
        voice_thread = threading.Thread(
            target=voice_listener_loop, args=(hud,), daemon=True
        )
        voice_thread.start()

    # Main logic thread
    logic_thread = threading.Thread(
        target=kora_logic, args=(hud,), daemon=True
    )
    logic_thread.start()

    # Reminder checker
    reminder_thread = threading.Thread(
        target=reminder_loop, args=(hud,), daemon=True
    )
    reminder_thread.start()

    sys.exit(app.exec())