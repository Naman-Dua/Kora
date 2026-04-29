import threading
import time
import os
import re
import ollama
from screen_analysis import capture_screen, get_available_vision_model
from settings import get_setting

class LiveEye(threading.Thread):
    def __init__(self, ui_log_callback, speak_callback, command_queue=None):
        super().__init__(daemon=True)
        self.ui_log = ui_log_callback
        self.speak = speak_callback
        self.command_queue = command_queue
        self.running = False
        self.interval = 45 # Slightly faster for proactivity
        self.last_observation = ""

    def run(self):
        self.running = True
        self.ui_log("SYSTEM", "Live Eye proactive monitoring started.")
        
        while self.running:
            if get_setting("enable_live_eye", False):
                self._observe()
            time.sleep(self.interval)

    def _observe(self):
        model_name = get_available_vision_model()
        if not model_name:
            return

        screenshot_path = None
        try:
            screenshot_path = capture_screen()
            
            prompt = """
Analyze this screen. Your goal is to be a PROACTIVE AI AGENT. 
If you see:
1. A coding error (Python traceback, terminal error): Suggest a fix or a research mission.
2. An interesting topic/article: Offer to summarize or research it.
3. A blank document or empty folder: Suggest a mission to populate it.
4. An app you can control (Spotify, VS Code) in a stalled state: Suggest a fix.

Format your response exactly as:
REASON: [Why you are speaking up]
PROPOSAL: [What mission/action you recommend]
COMMAND: [The exact command the user should say, e.g., 'mission fix my code' or 'research AI news']

If everything is CLEAR or normal, output: CLEAR
"""
            response = ollama.chat(
                model=model_name,
                messages=[{
                    "role": "user",
                    "content": prompt,
                    "images": [screenshot_path],
                }],
            )
            
            observation = response["message"]["content"].strip()
            
            if observation.upper() != "CLEAR" and observation != self.last_observation:
                self.ui_log("KORA (PROACTIVE)", observation)
                self.speak("I noticed something on your screen.")
                self.last_observation = observation
                
                # Proactive command injection
                if self.command_queue and "COMMAND:" in observation:
                    match = re.search(r"COMMAND:\s*(.+)$", observation, re.MULTILINE | re.IGNORECASE)
                    if match:
                        suggested_cmd = match.group(1).strip()
                        self.ui_log("SYSTEM", f"Proactive command detected: {suggested_cmd}")
                        # For now, we just suggest it. We could auto-queue it if we want full autonomy.
                
        except Exception as e:
            print(f"[LIVE EYE ERROR] {e}")
        finally:
            if screenshot_path and os.path.exists(screenshot_path):
                os.remove(screenshot_path)

    def stop(self):
        self.running = False
