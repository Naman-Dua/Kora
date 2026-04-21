import os
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

import sounddevice as sd
import soundfile as sf
import numpy as np
from faster_whisper import WhisperModel
import re

# Whisper STT — forced CPU mode (CUDA Toolkit not installed on this system).
# The 'base' model is already cached locally.
model = WhisperModel("base", device="cpu", compute_type="int8")
print("[EARS] Whisper 'base' loaded on CPU.")

SAMPLE_RATE = 16000
SILENCE_THRESHOLD = 0.015     # RMS energy below this = silence
SILENCE_DURATION = 1.5        # Seconds of silence before we consider speech done
MIN_SPEECH_DURATION = 0.5     # Ignore bursts shorter than this (noise filtering)
MAX_RECORD_SECONDS = 30       # Safety cap so it never records forever
CHUNK_DURATION = 0.1          # Read audio in 100ms chunks
WAKE_WORD_PATTERNS = [
    re.compile(r"\bhey\s+kora\b", re.IGNORECASE),
    re.compile(r"\bhi\s+kora\b", re.IGNORECASE),
    re.compile(r"\bwake\s+up\s+kora\b", re.IGNORECASE),
    re.compile(r"\bkora\s+wake\s+up\b", re.IGNORECASE),
]

def listen():
    """
    Smart Voice Activity Detection (VAD) listener.
    Waits for the user to start speaking, records everything,
    and stops the instant they go silent for SILENCE_DURATION seconds.
    """
    filename = "temp_audio.wav"
    print("\n--- Listening (speak now, I'll stop when you pause)... ---")

    audio_chunks = []
    silent_time = 0.0
    speech_started = False
    total_time = 0.0

    with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype='float32') as stream:
        while total_time < MAX_RECORD_SECONDS:
            # Read a small chunk of audio
            chunk, _ = stream.read(int(SAMPLE_RATE * CHUNK_DURATION))
            total_time += CHUNK_DURATION

            # Calculate the energy (volume) of this chunk
            rms = float(np.sqrt(np.mean(chunk ** 2)))

            if rms > SILENCE_THRESHOLD:
                # User is speaking!
                speech_started = True
                silent_time = 0.0
                audio_chunks.append(chunk.copy())
            else:
                if speech_started:
                    # User went quiet — start counting silence
                    audio_chunks.append(chunk.copy())  # keep the trailing silence for clean audio
                    silent_time += CHUNK_DURATION

                    if silent_time >= SILENCE_DURATION:
                        # They've been quiet long enough — sentence is done!
                        print("--- Speech ended (silence detected). Processing... ---")
                        break

    # If we captured nothing meaningful, return empty
    if not speech_started or len(audio_chunks) < int(MIN_SPEECH_DURATION / CHUNK_DURATION):
        return ""

    # Combine all chunks into a single audio array and save
    audio_data = np.concatenate(audio_chunks, axis=0)
    sf.write(filename, audio_data, SAMPLE_RATE)

    # Transcribe with Whisper
    segments, _ = model.transcribe(filename, beam_size=5, language="en")
    text = " ".join([segment.text for segment in segments])

    if os.path.exists(filename):
        os.remove(filename)

    result = text.strip()
    if result:
        print(f"[HEARD]: {result}")
    return result

def extract_wake_command(text):
    """Return the command spoken after the wake word, or None if not activated."""
    if not text:
        return None

    normalized = " ".join(text.strip().split())
    for pattern in WAKE_WORD_PATTERNS:
        match = pattern.search(normalized)
        if match:
            return normalized[match.end():].strip(" ,.!?-")
    return None