import pyttsx3

def speak(text):
    engine = pyttsx3.init()
    voices = engine.getProperty('voices')
    engine.setProperty('voice', voices[0].id) # 0 for male, 1 for female
    engine.setProperty('rate', 180)
    
    print(f"JARVIS: {text}")
    engine.say(text)
    engine.runAndWait()