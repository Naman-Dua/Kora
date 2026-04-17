import os
import subprocess
import webbrowser

def perform_action(cmd):
    """Logic to actually DO things on your PC"""
    cmd = cmd.lower()

    if "open chrome" in cmd:
        webbrowser.open("https://www.google.com")
        return "Opening the browser, sir."

    elif "open youtube" in cmd:
        webbrowser.open("https://www.youtube.com")
        return "Accessing the media archives."

    elif "open code" in cmd or "open vs code" in cmd:
        # Update this path to where your VS Code is installed
        os.startfile(r"C:\Users\Naman Dua\AppData\Local\Programs\Microsoft VS Code\Code.exe")
        return "Initializing development environment."

    elif "open notepad" in cmd:
        subprocess.Popen(['notepad.exe'])
        return "Opening a fresh scratchpad."

    return None