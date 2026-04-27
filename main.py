import threading
import queue
import sys
import os
import re
import time
import traceback
import winsound
from datetime import datetime

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QCoreApplication

from gui import KoraDashboard
from brain import KoraBrain
from kora_operator import OperatorState, handle_operator_command
from settings import load_settings, save_settings
from tasks import ReminderManager, check_for_tasks
from voice import speak
from mode_select import ask_mode
from storage import log_telemetry, load_telemetry_summary
from live_eye import LiveEye
from knowledge_watcher import KnowledgeWatcher
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
APP_SETTINGS = load_settings()
ENABLE_WAKE_WORD = False
SPEAK_TEXT_REPLIES = False
WAKE_STATUS              = "LISTENING FOR WAKE WORD"
COMMAND_STATUS           = "LISTENING FOR COMMAND"
DEFAULT_LISTENING_STATUS = "LISTENING..."
SLEEPING_STATUS          = "SLEEPING..."
ALERT_REPEAT_INTERVAL    = 10
MAX_ALERT_REPEATS        = 6
SESSION_ID = datetime.now().strftime("%Y%m%d-%H%M%S")
extract_wake_command = None
listen = None
calibrate_microphone = None
operator_state = OperatorState()

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
    "got it", "okay", "ok", "okay thanks", "okay thank you",
    "reminder off", "reminders off",
}
TEXT_WAKE_PATTERNS = (
    re.compile(r"^\s*(?:hey|hi)\s+kora\b", re.IGNORECASE),
    re.compile(r"^\s*wake\s+up\s+kora\b", re.IGNORECASE),
    re.compile(r"^\s*kora\s+wake\s+up\b", re.IGNORECASE),
)


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


def extract_text_wake_command(cmd):
    text = str(cmd).strip()
    for pattern in TEXT_WAKE_PATTERNS:
        match = pattern.match(text)
        if match:
            return text[match.end():].strip(" ,.!?-")
    return None


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


def should_speak_response(source):
    if source == "voice":
        return True
    return bool(SPEAK_TEXT_REPLIES)


def push_telemetry(ui, event_name, source=None, value=None):
    """Store telemetry and refresh the dashboard metrics."""
    try:
        log_telemetry(event_name, source=source, value=value, session_id=SESSION_ID)
        ui.telemetry_signal.emit(load_telemetry_summary())
    except Exception:
        # Telemetry should never break assistant behavior.
        pass


def refresh_runtime_settings():
    global APP_SETTINGS, ENABLE_WAKE_WORD, SPEAK_TEXT_REPLIES, DEFAULT_LISTENING_STATUS
    APP_SETTINGS = load_settings()
    ENABLE_WAKE_WORD = bool(APP_SETTINGS.get("enable_wake_word", False))
    SPEAK_TEXT_REPLIES = bool(APP_SETTINGS.get("speak_text_replies", False))
    DEFAULT_LISTENING_STATUS = WAKE_STATUS if ENABLE_WAKE_WORD else "LISTENING..."


def handle_settings_command(query):
    normalized = normalize_voice_command(query)

    if normalized in {"settings", "show settings", "list settings"}:
        state = "on" if APP_SETTINGS.get("enable_wake_word") else "off"
        typed = "on" if APP_SETTINGS.get("speak_text_replies") else "off"
        confirm = "on" if APP_SETTINGS.get("require_action_confirmation") else "off"
        model_name = APP_SETTINGS.get("model_name", "llama3.1:8b")
        return (
            "Current settings: "
            f"wake word {state}, typed reply speech {typed}, confirmations {confirm}, model {model_name}."
        )

    if normalized in {"wake word on", "turn wake word on", "enable wake word"}:
        save_settings({"enable_wake_word": True})
        refresh_runtime_settings()
        return "Wake word is on."

    if normalized in {"wake word off", "turn wake word off", "disable wake word"}:
        save_settings({"enable_wake_word": False})
        refresh_runtime_settings()
        return "Wake word is off."

    if normalized in {"typed replies on", "speak typed replies on", "turn typed replies on"}:
        save_settings({"speak_text_replies": True})
        refresh_runtime_settings()
        return "Typed replies will be spoken now."

    if normalized in {"typed replies off", "speak typed replies off", "turn typed replies off"}:
        save_settings({"speak_text_replies": False})
        refresh_runtime_settings()
        return "Typed replies will stay text-only now."

    if normalized in {"confirmations on", "turn confirmations on", "require confirmations"}:
        save_settings({"require_action_confirmation": True})
        refresh_runtime_settings()
        return "Safety confirmations are on."

    if normalized in {"confirmations off", "turn confirmations off", "skip confirmations"}:
        save_settings({"require_action_confirmation": False})
        refresh_runtime_settings()
        return "Safety confirmations are off."

    if normalized in {"live eye on", "turn live eye on", "enable vision monitoring"}:
        save_settings({"enable_live_eye": True})
        refresh_runtime_settings()
        return "Live Eye proactive vision is now active."

    if normalized in {"live eye off", "turn live eye off", "disable vision monitoring"}:
        save_settings({"enable_live_eye": False})
        refresh_runtime_settings()
        return "Live Eye is now inactive."

    model_match = re.match(r"^(?:set model to|use model)\s+(.+)$", normalized)
    if model_match:
        model_name = model_match.group(1).strip()
        save_settings({"model_name": model_name})
        refresh_runtime_settings()
        brain.model_name = model_name
        return f"Model updated to {model_name}."

    return None


def ensure_voice_stack_loaded():
    """Import the voice pipeline only after the user enables voice mode."""
    global extract_wake_command, listen, calibrate_microphone
    if extract_wake_command and listen and calibrate_microphone:
        return

    from ears import (
        extract_wake_command as _extract_wake_command,
        listen as _listen,
        calibrate_microphone as _calibrate_microphone,
    )

    extract_wake_command = _extract_wake_command
    listen = _listen
    calibrate_microphone = _calibrate_microphone


refresh_runtime_settings()


# ── Voice listener thread ─────────────────────────────────────────────────────

def voice_listener_loop(ui):
    """
    Runs forever in a background thread.
    Listens for voice commands and puts them into command_queue.
    Completely independent of the text input path.
    """
    ensure_voice_stack_loaded()
    while True:
        # Wait if Kora is busy processing or speaking
        while kora_busy.is_set():
            time.sleep(0.1)

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
                    time.sleep(0.5)
                continue

            if not ENABLE_WAKE_WORD:
                ui.status_signal.emit(DEFAULT_LISTENING_STATUS)
                heard = listen()
                if heard:
                    command_queue.put({"text": heard, "source": "voice"})
                    time.sleep(0.5)
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
                time.sleep(0.5)
            else:
                ui.log_signal.emit("SYSTEM", "Wake word detected.")
                ui.status_signal.emit(COMMAND_STATUS)
                speak("Yes?")
                follow_up = listen()
                if follow_up:
                    command_queue.put({"text": follow_up, "source": "voice"})
                    time.sleep(0.5)

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
                push_telemetry(ui, "reminder_triggered", source=item.kind, value=item.task)
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
    push_telemetry(ui, "session_started", source=INPUT_MODE, value="kora_online")

    # Only calibrate mic if voice input is active
    if INPUT_MODE in ("voice", "both"):
        ensure_voice_stack_loaded()
        ui.status_signal.emit("CALIBRATING MIC...")
        ui.log_signal.emit("SYSTEM", "Calibrating microphone — stay silent for 2 seconds...")
        kora_busy.set()
        try:
            calibrate_microphone(duration=2.0)
        finally:
            kora_busy.clear()
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
        push_telemetry(ui, "command_received", source=source, value=query[:140])

        cmd = query.lower()

        try:
            # ── Shutdown ──────────────────────────────────────────────────────
            if cmd.strip() in SHUTDOWN_COMMANDS:
                ui.log_signal.emit("SYSTEM", "Shutting down. Goodbye.")
                speak("Goodbye.")
                push_telemetry(ui, "session_shutdown", source=source, value="user_requested")
                QCoreApplication.quit()
                os._exit(0)

            norm_cmd = normalize_voice_command(cmd)
            if sleep_mode.is_set():
                wake_cmd = extract_text_wake_command(query) if source == "text" else None
                if wake_cmd is None:
                    r = "I'm sleeping right now. Say or type Hey Kora to wake me."
                    ui.log_signal.emit("KORA", r)
                    speak(r)
                    ui.status_signal.emit(SLEEPING_STATUS)
                    ui.re_enable_input()
                    kora_busy.clear()
                    continue
                sleep_mode.clear()
                wake_notice_pending.set()
                handle_wake_transition()
                if wake_cmd:
                    command_queue.put({"text": wake_cmd, "source": source})
                ui.re_enable_input()
                kora_busy.clear()
                continue

            # ── Recalibrate ───────────────────────────────────────────────────
            if command_matches(norm_cmd, RECALIBRATE_COMMANDS):
                if INPUT_MODE == "text" or calibrate_microphone is None:
                    r = "Microphone recalibration is not available in text-only mode."
                    ui.log_signal.emit("KORA", r)
                    if should_speak_response(source):
                        speak(r)
                    ui.status_signal.emit(DEFAULT_LISTENING_STATUS)
                    ui.re_enable_input()
                    kora_busy.clear()
                    continue
                r = "Recalibrating microphone. Please stay silent for 2 seconds."
                ui.log_signal.emit("KORA", r)
                speak(r)
                push_telemetry(ui, "mic_recalibration", source=source, value="requested")
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
                push_telemetry(ui, "conversation_reset", source=source, value="clear_history")
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
                if dismissed:
                    removed = 0
                    if norm_cmd in {"reminder off", "reminders off"}:
                        removed = reminder_manager.cancel_all()
                    push_telemetry(ui, "alerts_dismissed", source=source, value=str(dismissed))
                    r = f"Stopped {dismissed} active alert{'s' if dismissed != 1 else ''}."
                    if removed:
                        r += f" Cleared {removed} pending reminder{'s' if removed != 1 else ''}."
                    ui.log_signal.emit("KORA", r)
                    speak(r)
                    ui.status_signal.emit(DEFAULT_LISTENING_STATUS)
                    ui.re_enable_input()
                    kora_busy.clear()
                    continue

            # ── Sleep ─────────────────────────────────────────────────────────
            if is_sleep_request(cmd):
                sleep_mode.set()
                push_telemetry(ui, "sleep_mode_entered", source=source, value="sleep")
                r = "Going to sleep. Say Hey Kora to wake me."
                ui.log_signal.emit("KORA", r)
                speak(r)
                ui.status_signal.emit(SLEEPING_STATUS)
                ui.re_enable_input()
                kora_busy.clear()
                continue

            # ── Settings ──────────────────────────────────────────────────────
            settings_reply = handle_settings_command(query)
            if settings_reply:
                push_telemetry(ui, "settings_changed", source=source, value=settings_reply[:140])
                ui.log_signal.emit("KORA", settings_reply)
                if should_speak_response(source):
                    ui.status_signal.emit("SPEAKING...")
                    speak(settings_reply)
                ui.status_signal.emit(DEFAULT_LISTENING_STATUS)
                ui.re_enable_input()
                kora_busy.clear()
                continue

            # ── Operator (Actions, Screen, Search, Skills, Automations) ───────
            operator_res = handle_operator_command(query, APP_SETTINGS, operator_state, reminder_manager)
            if operator_res:
                action_name = operator_res.get("action", "unknown")
                reply_text = operator_res.get("reply", "")
                push_telemetry(ui, f"operator_{action_name}", source=source, value=reply_text[:140])
                ui.log_signal.emit("KORA", reply_text)
                if should_speak_response(source):
                    ui.status_signal.emit("SPEAKING...")
                    speak(reply_text)
                ui.status_signal.emit(DEFAULT_LISTENING_STATUS)
                ui.re_enable_input()
                kora_busy.clear()
                continue

            # ── Tasks / reminders ─────────────────────────────────────────────
            task = check_for_tasks(cmd, reminder_manager)
            if task:
                if task.get("action") == "cancel_all":
                    dismissed = dismiss_all_alerts()
                    if dismissed:
                        task["reply"] = (
                            f"{task['reply']} Stopped {dismissed} active alert"
                            f"{'s' if dismissed != 1 else ''}."
                        )
                push_telemetry(ui, "task_event", source=source, value=task.get("action", "unknown"))
                ui.log_signal.emit("KORA", task["reply"])
                if should_speak_response(source):
                    ui.status_signal.emit("SPEAKING...")
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

            # ── Conversation summarizer ───────────────────────────────────────
            from conversation_summarizer import is_summarize_request, summarize_conversation
            if is_summarize_request(query):
                res = summarize_conversation(brain.conversation_history, brain.model_name)
                push_telemetry(ui, "conversation_summary", source=source, value=res[:140])
                ui.log_signal.emit("KORA", res)
                if should_speak_response(source):
                    ui.status_signal.emit("SPEAKING...")
                    speak(res)
                ui.status_signal.emit(DEFAULT_LISTENING_STATUS)
                ui.re_enable_input()
                kora_busy.clear()
                continue

            # ── General reply (LLM) ───────────────────────────────────────────
            res = brain.generate_reply(query)
            
            # Run fact extraction in background after the reply is ready
            threading.Thread(
                target=brain.learn, args=(query,), daemon=True
            ).start()
            push_telemetry(ui, "llm_reply", source=source, value=res[:140])
            ui.log_signal.emit("KORA", res)

            if should_speak_response(source):
                ui.status_signal.emit("SPEAKING...")
                speak(res)

            ui.status_signal.emit(DEFAULT_LISTENING_STATUS)
            ui.re_enable_input()
            kora_busy.clear()

        except Exception as e:
            err = f"Error: {str(e)}"
            ui.log_signal.emit("SYSTEM ERROR", err)
            push_telemetry(ui, "error", source="logic", value=str(e)[:180])
            print(f"[Logic error]: {traceback.format_exc()}")
            ui.status_signal.emit("RECOVERED")
            ui.re_enable_input()
            kora_busy.clear()


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = QApplication(sys.argv)

    # ── Show mode selector before anything else ───────────────────────────────
    INPUT_MODE = ask_mode()          # blocks until user picks, then returns
    if INPUT_MODE in ("voice", "both"):
        ensure_voice_stack_loaded()

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

    # Start proactive vision
    live_eye = LiveEye(hud.log_signal.emit, speak, command_queue=command_queue)
    live_eye.start()

    # Start knowledge watcher
    knowledge_watcher = KnowledgeWatcher(hud.log_signal.emit)
    knowledge_watcher.start()

    sys.exit(app.exec())
