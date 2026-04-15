from ears import listen # Use your faster-whisper code
from voice import speak # Use your pyttsx3 code
from vision import scan_for_master
from monitor import get_system_vitals, check_health
from search_engine import search_online
from jarvis_engine import JarvisBrain

brain = JarvisBrain()

def run_jarvis():
    # 1. Security Check
    if not scan_for_master():
        print("Unauthorized access.")
        return

    speak("Recognition complete. All systems nominal. How can I help, sir?")

    while True:
        # 2. Check Hardware Health
        alert = check_health()
        if alert: speak(alert)

        # 3. Process Commands
        user_input = listen()
        if not user_input or len(user_input) < 3: continue
        
        cmd = user_input.lower()

        if "search" in cmd:
            query = cmd.replace("search", "").strip()
            speak(f"Scanning the web for {query}...")
            info = search_online(query)
            brain.learn(info)
            speak(info)

        elif "status" in cmd or "report" in cmd:
            v = get_system_vitals()
            speak(f"CPU at {v['cpu']} percent. Memory at {v['ram']} percent. Battery is {v['battery']}.")

        elif "go to sleep" in cmd or "exit" in cmd:
            speak("Powering down. Goodbye, sir.")
            break

        else:
            brain.learn(user_input)
            speak("I've stored that in my database.")

if __name__ == "__main__":
    run_jarvis()