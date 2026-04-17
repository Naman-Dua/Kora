import pyttsx3
import threading

# Initialize once at the top
engine = pyttsx3.init()
engine.setProperty('rate', 180)
engine.setProperty('volume', 1.0)

# Bug fix: use a threading lock instead of accessing private _inLoop attribute,
# which raises AttributeError on many pyttsx3 versions/platforms.
_speak_lock = threading.Lock()

def speak(text):
    print(f"AURA: {text}")
    with _speak_lock:
        engine.say(text)
        engine.runAndWait()