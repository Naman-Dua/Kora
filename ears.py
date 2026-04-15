import sounddevice as sd
import soundfile as sf
from faster_whisper import WhisperModel
import os

model = WhisperModel("base", device="cpu", compute_type="int8")

def listen():
    fs = 16000
    seconds = 5 
    filename = "temp_audio.wav"
    
    print("\n--- Listening... ---")
    myrecording = sd.rec(int(seconds * fs), samplerate=fs, channels=1)
    sd.wait()
    sf.write(filename, myrecording, fs)
    
    segments, _ = model.transcribe(filename, beam_size=5)
    text = " ".join([segment.text for segment in segments])
    
    if os.path.exists(filename):
        os.remove(filename)
        
    return text.strip()