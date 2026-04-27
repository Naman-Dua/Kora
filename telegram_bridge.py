import time
import threading
import requests
import os
from PIL import ImageGrab
from kora_operator import handle_operator_command, OperatorState
from settings import get_setting

class TelegramBridge:
    def __init__(self, ui_log_callback, speak_callback):
        self.token = get_setting("telegram_token", "")
        self.chat_id = get_setting("telegram_chat_id", "") # Authorized chat ID
        self.base_url = f"https://api.telegram.org/bot{self.token}"
        self.ui_log = ui_log_callback
        self.speak = speak_callback
        self.last_update_id = 0
        self.running = False
        self.operator_state = OperatorState()

    def send_message(self, text):
        if not self.token or not self.chat_id: return
        url = f"{self.base_url}/sendMessage"
        requests.post(url, json={"chat_id": self.chat_id, "text": text})

    def send_photo(self, photo_path):
        if not self.token or not self.chat_id: return
        url = f"{self.base_url}/sendPhoto"
        with open(photo_path, "rb") as f:
            requests.post(url, data={"chat_id": self.chat_id}, files={"photo": f})

    def poll(self):
        if not self.token:
            print("[TELEGRAM] No token found in settings.")
            return

        while self.running:
            try:
                url = f"{self.base_url}/getUpdates"
                params = {"offset": self.last_update_id + 1, "timeout": 30}
                res = requests.get(url, params=params, timeout=35).json()

                if res.get("ok"):
                    for update in res.get("result", []):
                        self.last_update_id = update["update_id"]
                        msg = update.get("message")
                        if not msg: continue
                        
                        text = msg.get("text", "")
                        from_id = str(msg.get("from", {}).get("id", ""))
                        if self.chat_id and from_id != self.chat_id: continue
                        if not self.chat_id: self.chat_id = from_id
                        
                        self.ui_log("MOBILE", text)
                        res = handle_operator_command(text, {"model_name": "llama3.1:8b"}, self.operator_state)
                        if res:
                            reply = res.get("reply", "Done.")
                            self.send_message(reply)
                            if "screenshot" in text.lower():
                                screenshot_path = "mobile_screen.png"
                                ImageGrab.grab().save(screenshot_path)
                                self.send_photo(screenshot_path)
                                os.remove(screenshot_path)
            except: time.sleep(10)

    def start(self):
        if not self.token: return
        self.running = True
        self.thread = threading.Thread(target=self.poll, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
