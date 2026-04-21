import threading
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
from ears import extract_wake_command, listen

brain = KoraBrain()
reminder_manager = ReminderManager()
sleep_mode = threading.Event()
wake_notice_pending = threading.Event()
active_alert_ids = set()
active_alerts_lock = threading.Lock()
ENABLE_WAKE_WORD = os.getenv("KORA_ENABLE_WAKE_WORD", "0").lower() in {"1", "true", "yes", "on"}
WAKE_STATUS = "LISTENING FOR WAKE WORD"
COMMAND_STATUS = "LISTENING FOR COMMAND"
DEFAULT_LISTENING_STATUS = WAKE_STATUS if ENABLE_WAKE_WORD else "LISTENING..."
SLEEPING_STATUS = "SLEEPING..."
ALERT_REPEAT_INTERVAL = 10
MAX_ALERT_REPEATS = 6
SHUTDOWN_COMMANDS = {
    "shutdown",
    "power down",
    "exit",
    "exit kora",
    "quit kora",
    "shutdown kora",
    "close kora",
}
RESET_COMMANDS = {
    "forget everything",
    "reset conversation",
    "clear memory",
    "start fresh",
    "wipe memory",
    "clear conversation",
}
SLEEP_COMMANDS = {
    "go to sleep",
    "sleep mode",
    "go silent",
    "be quiet",
    "stay quiet",
    "stop talking",
    "don't talk",
    "dont talk",
    "do not talk",
    "stop listening",
    "mute yourself",
}
DISMISS_ALERT_COMMANDS = {
    "dismiss reminder",
    "stop reminder",
    "stop the reminder",
    "dismiss the reminder",
    "dismiss timer",
    "stop timer",
    "stop the timer",
    "dismiss alert",
    "stop alert",
    "got it",
    "okay thanks",
    "okay thank you",
}


def normalize_voice_command(cmd):
    normalized = re.sub(r"[^a-z0-9'\s]+", " ", str(cmd).lower())
    normalized = re.sub(r"\b(kora|please)\b", " ", normalized)
    return " ".join(normalized.split())


def command_matches(normalized, phrases):
    for phrase in phrases:
        if normalized == phrase or f" {phrase} " in f" {normalized} ":
            return True
    return False


def is_sleep_request(cmd):
    normalized = normalize_voice_command(cmd)
    return command_matches(normalized, SLEEP_COMMANDS)


def is_dismiss_alert_request(cmd):
    normalized = normalize_voice_command(cmd)
    return command_matches(normalized, DISMISS_ALERT_COMMANDS)


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
def handle_wake_transition(ui):
    if not wake_notice_pending.is_set():
        return

    wake_notice_pending.clear()
    ui.log_signal.emit("SYSTEM", "Kora is awake again.")
    ui.status_signal.emit("SPEAKING...")
    speak("I'm awake.")
    ui.status_signal.emit(DEFAULT_LISTENING_STATUS)


def wait_for_command(ui):
    """Listen for a command, with wake-word gating only when explicitly enabled."""
    if sleep_mode.is_set():
        while True:
            ui.status_signal.emit(SLEEPING_STATUS)
            heard_text = listen()
            if not heard_text:
                continue

            wake_command = extract_wake_command(heard_text)
            if wake_command is None:
                continue

            sleep_mode.clear()
            wake_notice_pending.set()
            if wake_command:
                return wake_command
            return ""

    if not ENABLE_WAKE_WORD:
        ui.status_signal.emit(DEFAULT_LISTENING_STATUS)
        return listen()

    while True:
        ui.status_signal.emit(DEFAULT_LISTENING_STATUS)
        heard_text = listen()
        if not heard_text:
            continue

        command_after_wake = extract_wake_command(heard_text)
        if command_after_wake is None:
            continue

        if command_after_wake:
            return command_after_wake

        ui.log_signal.emit("SYSTEM", "Wake word detected.")
        ui.status_signal.emit(COMMAND_STATUS)
        speak("Yes?")
        follow_up = listen()
        if follow_up:
            return follow_up


def reminder_loop(ui):
    while True:
        try:
            due_items = reminder_manager.pop_due()
            for item in due_items:
                alert_thread = threading.Thread(
                    target=deliver_reminder_alert,
                    args=(ui, item),
                    daemon=True,
                )
                alert_thread.start()
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

            if was_sleeping and index == 0:
                ui.log_signal.emit("SYSTEM", "Reminder is interrupting sleep mode.")
            elif index > 0:
                ui.log_signal.emit("SYSTEM", f"Reminder follow-up {index + 1} of {MAX_ALERT_REPEATS}.")

            ui.log_signal.emit("REMINDER", message)
            ui.status_signal.emit("SPEAKING...")
            play_alert_tone()
            speak(message)
            ui.status_signal.emit(SLEEPING_STATUS if sleep_mode.is_set() else DEFAULT_LISTENING_STATUS)

            if index < MAX_ALERT_REPEATS - 1 and is_alert_active(item.id):
                time.sleep(ALERT_REPEAT_INTERVAL)
    finally:
        clear_active_alert(item.id)

def kora_logic(ui):
    ui.status_signal.emit("SYSTEM ONLINE")
    ui.log_signal.emit("SYSTEM", "Kora core initialized. Native graphics engaged.")
    speak("Welcome back. All systems are online and memory is loaded.")
    if ENABLE_WAKE_WORD:
        ui.log_signal.emit("SYSTEM", "Wake word mode enabled.")
    else:
        ui.log_signal.emit("SYSTEM", "Wake word mode disabled. Direct listening active.")
    ui.status_signal.emit(DEFAULT_LISTENING_STATUS)

    while True:
        try:
            query = wait_for_command(ui)
            handle_wake_transition(ui)
            if not query:
                continue
            ui.log_signal.emit("USER", query)
            ui.status_signal.emit("PROCESSING...")
            cmd = query.lower()

            # INSTANT POWER DOWN (Zero Freezing)
            if cmd.strip() in SHUTDOWN_COMMANDS:
                ui.log_signal.emit("SYSTEM", "Shutting down immediately. Goodbye.")
                print("\nKORA: Shutting down immediately.")
                QCoreApplication.quit()
                os._exit(0) # Immediate OS-level process kill

            # Conversation reset (clears DB log + RAM history)
            normalized_cmd = normalize_voice_command(cmd)
            if command_matches(normalized_cmd, RESET_COMMANDS):
                brain.reset_conversation()
                reset_reply = "Done. Conversation history cleared. Starting fresh."
                ui.log_signal.emit("KORA", reset_reply)
                ui.status_signal.emit("SPEAKING...")
                speak(reset_reply)
                ui.status_signal.emit(DEFAULT_LISTENING_STATUS)
                continue

            if is_dismiss_alert_request(cmd):
                dismissed = dismiss_all_alerts()
                dismiss_reply = (
                    f"Stopped {dismissed} active reminder alert{'s' if dismissed != 1 else ''}."
                    if dismissed
                    else "There is no active reminder alert right now."
                )
                ui.log_signal.emit("KORA", dismiss_reply)
                ui.status_signal.emit("SPEAKING...")
                speak(dismiss_reply)
                ui.status_signal.emit(SLEEPING_STATUS if sleep_mode.is_set() else DEFAULT_LISTENING_STATUS)
                continue

            if is_sleep_request(cmd):
                sleep_mode.set()
                sleep_reply = "Going to sleep. Say Hey Kora to wake me."
                ui.log_signal.emit("KORA", sleep_reply)
                ui.status_signal.emit("SPEAKING...")
                speak(sleep_reply)
                ui.status_signal.emit(SLEEPING_STATUS)
                continue

            # Desktop Action Logic
            action_reply = perform_action(cmd)
            if action_reply:
                ui.log_signal.emit("KORA", action_reply)
                ui.status_signal.emit("SPEAKING...")
                speak(action_reply)
                ui.status_signal.emit(DEFAULT_LISTENING_STATUS)
                continue

            if is_screen_request(cmd):
                screen_reply = analyze_screen(query)
                ui.log_signal.emit("KORA", screen_reply)
                ui.status_signal.emit("SPEAKING...")
                speak(screen_reply)
                ui.status_signal.emit(DEFAULT_LISTENING_STATUS)
                continue

            # Task/Reminder Logic
            task = check_for_tasks(cmd, reminder_manager)
            if task:
                ui.log_signal.emit("KORA", task["reply"])
                ui.status_signal.emit("SPEAKING...")
                speak(task["reply"])
                if task.get("action") == "schedule" and task.get("item"):
                    brain.learn(
                        f"{task['item'].kind.upper()} scheduled: {task['item'].task} at {task['item'].due_phrase()}"
                    )
                ui.status_signal.emit("TASK LOGGED")
                ui.status_signal.emit(DEFAULT_LISTENING_STATUS)
                continue

            # General Reply
            brain.learn(query)
            
            res = brain.generate_reply(query)
            
            ui.log_signal.emit("KORA", res)
            ui.status_signal.emit("SPEAKING...")
            speak(res)
            ui.status_signal.emit(DEFAULT_LISTENING_STATUS)
            
        except Exception as e:
            err_msg = f"Crash prevented: {str(e)}"
            ui.log_signal.emit("SYSTEM ERROR", err_msg)
            print(f"Exception logic branch: {traceback.format_exc()}")
            ui.status_signal.emit("RECOVERED")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    hud = KoraDashboard()
    hud.show()

    # Start logic thread
    t = threading.Thread(target=kora_logic, args=(hud,), daemon=True)
    t.start()
    reminder_thread = threading.Thread(target=reminder_loop, args=(hud,), daemon=True)
    reminder_thread.start()

    sys.exit(app.exec())