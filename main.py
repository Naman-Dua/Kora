import threading
import sys
import os
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QCoreApplication
from gui import AuraHUD
from brain import AuraBrain
from tasks import check_for_tasks
from voice import speak
from ears import listen

brain = AuraBrain()

def aura_logic(ui):
    speak("Welcome back, sir. Systems are online.")
    ui.status_signal.emit("SYSTEM ONLINE")

    while True:
        query = listen()
        if not query: continue
        
        ui.status_signal.emit("PROCESSING...")
        cmd = query.lower()

        # FIXED POWER DOWN (No Freezing)
        if any(word in cmd for word in ["shutdown", "power down", "exit"]):
            speak("Powering down. Goodbye, sir.")
            QCoreApplication.quit()
            os._exit(0) # Immediate terminal-level kill

        # Task/Reminder Logic
        task = check_for_tasks(cmd)
        if task:
            speak(task["reply"])
            brain.learn(f"TASK: {task['task']}")
            ui.status_signal.emit("TASK LOGGED")
            continue

        # General Reply
        brain.learn(query)
        res = brain.generate_reply(query)
        speak(res)
        ui.status_signal.emit("SYSTEM ONLINE")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    hud = AuraHUD()
    hud.show()

    # Start logic thread
    t = threading.Thread(target=aura_logic, args=(hud,), daemon=True)
    t.start()

    sys.exit(app.exec())