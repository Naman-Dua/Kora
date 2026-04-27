import asyncio
import os
import subprocess
import tempfile
import threading

import pyttsx3

try:
    import edge_tts
except ImportError:
    edge_tts = None

EDGE_VOICE = os.getenv("KORA_EDGE_VOICE", "en-US-AriaNeural")
WINDOWS_POWERSHELL = r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
_speak_lock = threading.Lock()


def _escape_powershell_string(text):
    return str(text).replace("'", "''")


def _run_powershell(script):
    subprocess.run(
        [WINDOWS_POWERSHELL, "-NoProfile", "-Command", script],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


async def _save_edge_tts(text, output_path):
    communicate = edge_tts.Communicate(text=text, voice=EDGE_VOICE)
    await communicate.save(output_path)


def _play_mp3(output_path):
    safe_path = _escape_powershell_string(output_path)
    script = (
        "Add-Type -AssemblyName presentationCore; "
        "$player = New-Object System.Windows.Media.MediaPlayer; "
        f"$player.Open([System.Uri]::new('{safe_path}')); "
        "$player.Volume = 1.0; "
        "$player.Play(); "
        "while ($player.NaturalDuration.TimeSpan.TotalMilliseconds -le 0) { "
        "Start-Sleep -Milliseconds 100 "
        "} "
        "$duration = [math]::Ceiling($player.NaturalDuration.TimeSpan.TotalMilliseconds) + 400; "
        "Start-Sleep -Milliseconds $duration; "
        "$player.Stop(); "
        "$player.Close();"
    )
    _run_powershell(script)


def _speak_with_edge(text):
    temp_file = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as temp:
            temp_file = temp.name

        asyncio.run(_save_edge_tts(text, temp_file))
        _play_mp3(temp_file)
    finally:
        if temp_file and os.path.exists(temp_file):
            os.remove(temp_file)


def _speak_with_windows_voice(text):
    escaped_text = _escape_powershell_string(text)
    script = (
        "Add-Type -AssemblyName System.Speech; "
        "$speaker = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
        "$speaker.Volume = 100; "
        "$speaker.Rate = 2; "
        f"$speaker.Speak('{escaped_text}');"
    )
    _run_powershell(script)


def _speak_with_pyttsx3(text):
    engine = pyttsx3.init()
    engine.setProperty("rate", 180)
    engine.setProperty("volume", 1.0)
    engine.say(text)
    engine.runAndWait()
    engine.stop()


def speak(text):
    cleaned = " ".join(str(text).split())
    if not cleaned:
        return

    print(f"KORA: {cleaned}")
    with _speak_lock:
        if edge_tts is not None:
            try:
                _speak_with_edge(cleaned)
                return
            except Exception as exc:
                print(f"[VOICE] Edge TTS failed, falling back to Windows voice: {exc}")

        try:
            _speak_with_windows_voice(cleaned)
            return
        except Exception as exc:
            print(f"[VOICE] Windows voice failed, falling back to pyttsx3: {exc}")

        _speak_with_pyttsx3(cleaned)