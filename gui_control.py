import pyautogui
import time
import re

# Safety settings
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.5

GUI_PATTERNS = [
    re.compile(r"^(?:click|press) (?:on )?(?:the )?(.+)$", re.I),
    re.compile(r"^type\s+\"(.+?)\"\s*(?:into|on)?\s*(?:the )?(.+)?$", re.I),
    re.compile(r"^scroll (up|down)$", re.I),
    re.compile(r"^(?:press|hit) (?:the )?key (.+)$", re.I),
]

def is_gui_request(text):
    normalized = " ".join(str(text).strip().split())
    return any(p.match(normalized) for p in GUI_PATTERNS)

def handle_gui_command(text):
    normalized = " ".join(str(text).strip().split())
    
    # Click (Currently simple coordinate-based or keyboard shortcuts)
    # Full CV-based clicking requires more setup, so we'll start with keys and shortcuts
    m = re.match(r"^(?:click|press) (?:on )?(?:the )?(.+)$", normalized, re.I)
    if m:
        target = m.group(1).lower()
        if "start" in target:
            pyautogui.press('win')
            return {"action": "gui_click", "reply": "Pressed the Start button."}
        if "enter" in target:
            pyautogui.press('enter')
            return {"action": "gui_click", "reply": "Pressed Enter."}
        # Add more mappings or generic key presses
        try:
            pyautogui.press(target)
            return {"action": "gui_click", "reply": f"Pressed the {target} key."}
        except:
            pass

    # Type
    m = re.match(r"^type\s+\"(.+?)\"\s*(?:into|on)?\s*(?:the )?(.+)?$", normalized, re.I)
    if m:
        content = m.group(1)
        pyautogui.write(content, interval=0.1)
        return {"action": "gui_type", "reply": f"Typed: {content}"}

    # Scroll
    m = re.match(r"^scroll (up|down)$", normalized, re.I)
    if m:
        direction = m.group(1).lower()
        amount = 500 if direction == "up" else -500
        pyautogui.scroll(amount)
        return {"action": "gui_scroll", "reply": f"Scrolled {direction}."}

    return None

def autonomous_gui_action(action_type, payload):
    """
    Called by Mission Control or Live Eye to perform specific UI tasks.
    """
    if action_type == "type":
        pyautogui.write(payload)
    elif action_type == "press":
        pyautogui.press(payload)
    elif action_type == "hotkey":
        pyautogui.hotkey(*payload)
    elif action_type == "click_at":
        pyautogui.click(payload['x'], payload['y'])
