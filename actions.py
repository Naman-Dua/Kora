import os
import re
import subprocess
import webbrowser

LOCALAPPDATA = os.getenv("LOCALAPPDATA", "")
PROGRAMFILES = os.getenv("PROGRAMFILES", "")
PROGRAMFILES_X86 = os.getenv("PROGRAMFILES(X86)", "")
APPDATA = os.getenv("APPDATA", "")

APP_TARGETS = {
    "chrome": {
        "aliases": ["google chrome", "chrome", "browser"],
        "paths": [
            os.path.join(PROGRAMFILES, "Google", "Chrome", "Application", "chrome.exe"),
            os.path.join(PROGRAMFILES_X86, "Google", "Chrome", "Application", "chrome.exe"),
        ],
        "fallback": ["cmd", "/c", "start", "", "chrome"],
        "processes": ["chrome.exe"],
        "reply": "Opening Chrome.",
        "close_name": "Chrome",
    },
    "vs_code": {
        "aliases": ["visual studio code", "vs code", "vscode", "code editor", "code"],
        "paths": [
            os.path.join(LOCALAPPDATA, "Programs", "Microsoft VS Code", "Code.exe"),
        ],
        "fallback": ["cmd", "/c", "start", "", "code"],
        "processes": ["Code.exe"],
        "reply": "Launching Visual Studio Code.",
        "close_name": "Visual Studio Code",
    },
    "spotify": {
        "aliases": ["spotify", "music app"],
        "paths": [
            os.path.join(APPDATA, "Spotify", "Spotify.exe"),
            os.path.join(LOCALAPPDATA, "Microsoft", "WindowsApps", "Spotify.exe"),
        ],
        "fallback": ["cmd", "/c", "start", "", "spotify"],
        "processes": ["Spotify.exe"],
        "reply": "Launching Spotify.",
        "close_name": "Spotify",
    },
    "notepad": {
        "aliases": ["notepad", "text editor"],
        "command": ["notepad.exe"],
        "processes": ["notepad.exe"],
        "reply": "Opening Notepad.",
        "close_name": "Notepad",
    },
    "calculator": {
        "aliases": ["calculator", "calc"],
        "command": ["calc.exe"],
        "processes": ["CalculatorApp.exe", "calc.exe"],
        "reply": "Opening Calculator.",
        "close_name": "Calculator",
    },
    "explorer": {
        "aliases": ["file explorer", "windows explorer", "explorer", "files"],
        "command": ["explorer.exe"],
        "processes": ["explorer.exe"],
        "reply": "Opening File Explorer.",
        "close_name": "File Explorer",
    },
    "paint": {
        "aliases": ["paint", "mspaint"],
        "command": ["mspaint.exe"],
        "processes": ["mspaint.exe"],
        "reply": "Opening Paint.",
        "close_name": "Paint",
    },
    "task_manager": {
        "aliases": ["task manager"],
        "command": ["taskmgr.exe"],
        "processes": ["Taskmgr.exe"],
        "reply": "Opening Task Manager.",
        "close_name": "Task Manager",
    },
    "cmd": {
        "aliases": ["command prompt", "cmd", "terminal"],
        "command": ["cmd.exe"],
        "processes": ["cmd.exe", "WindowsTerminal.exe"],
        "reply": "Opening Command Prompt.",
        "close_name": "Command Prompt",
    },
    "powershell": {
        "aliases": ["powershell", "windows powershell"],
        "command": ["powershell.exe"],
        "processes": ["powershell.exe", "pwsh.exe"],
        "reply": "Opening PowerShell.",
        "close_name": "PowerShell",
    },
    "settings": {
        "aliases": ["settings", "windows settings"],
        "command": ["cmd", "/c", "start", "", "ms-settings:"],
        "reply": "Opening Settings.",
        "close_name": "Settings",
        "close_unsupported": True,
    },
}

WEB_TARGETS = {
    "youtube": ("YouTube", "https://www.youtube.com"),
    "github": ("GitHub", "https://github.com"),
    "gmail": ("Gmail", "https://mail.google.com"),
    "google": ("Google", "https://www.google.com"),
    "reddit": ("Reddit", "https://www.reddit.com"),
}

OPEN_VERBS = ("open", "launch", "start", "run")
CLOSE_VERBS = ("close", "quit", "stop", "exit")
ACTION_PATTERNS = {
    "open": re.compile(r"\b(open|launch|start|run)\b"),
    "close": re.compile(r"\b(close|quit|stop|exit)\b"),
}
LEADING_FILLER_PATTERN = re.compile(
    r"^(?:hey kora|kora|can you|could you|would you|please|hey|hi|just|for me)\s+",
    re.IGNORECASE,
)
TRAILING_FILLER_PATTERN = re.compile(
    r"\s+(?:please|for me|right now|now|thanks|thank you)$",
    re.IGNORECASE,
)
TARGET_PREFIX_PATTERN = re.compile(r"^(?:the|my|a|an)\s+", re.IGNORECASE)
TARGET_SUFFIX_PATTERN = re.compile(
    r"\s+(?:app|application|program|window)\s*$",
    re.IGNORECASE,
)


def _normalize(text):
    cleaned = re.sub(r"[?!,.;:]+", " ", str(text).lower())
    cleaned = LEADING_FILLER_PATTERN.sub("", cleaned)
    cleaned = TRAILING_FILLER_PATTERN.sub("", cleaned)
    return " ".join(cleaned.split())


def _extract_action_target(command_text):
    for action, pattern in ACTION_PATTERNS.items():
        match = pattern.search(command_text)
        if not match:
            continue

        target = command_text[match.end():].strip()
        target = TARGET_PREFIX_PATTERN.sub("", target)
        target = TARGET_SUFFIX_PATTERN.sub("", target)
        target = " ".join(target.split())
        if target:
            return action, target
    return None, None


def _resolve_app(target_text):
    best_match = None
    best_length = -1

    for app in APP_TARGETS.values():
        for alias in app["aliases"]:
            alias_pattern = rf"(^|\b){re.escape(alias)}(\b|$)"
            if re.search(alias_pattern, target_text):
                if len(alias) > best_length:
                    best_match = app
                    best_length = len(alias)

    return best_match


def _resolve_web(target_text):
    best_match = None
    best_length = -1

    for alias, details in WEB_TARGETS.items():
        alias_pattern = rf"(^|\b){re.escape(alias)}(\b|$)"
        if re.search(alias_pattern, target_text):
            if len(alias) > best_length:
                best_match = details
                best_length = len(alias)

    return best_match


def _launch_app(app):
    for path in app.get("paths", []):
        if path and os.path.exists(path):
            os.startfile(path)
            return True

    command = app.get("command") or app.get("fallback")
    if command:
        subprocess.Popen(command)
        return True
    return False


def _close_app(app):
    if app.get("close_unsupported"):
        return "unsupported"

    for process_name in app.get("processes", []):
        result = subprocess.run(
            ["taskkill", "/IM", process_name, "/F"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return True
    return False


def perform_action(cmd):
    """Handle direct desktop open/close commands before routing to the LLM."""
    command_text = _normalize(cmd)
    action, target_text = _extract_action_target(command_text)
    if not action or not target_text:
        return None

    web_target = _resolve_web(target_text)
    if action == "open" and web_target:
        label, url = web_target
        webbrowser.open(url)
        return f"Opening {label}."

    app = _resolve_app(target_text)
    if not app:
        return None

    if action == "open":
        if _launch_app(app):
            return app["reply"]
        return f"I recognized {app['close_name']}, but I could not launch it on this PC."

    close_result = _close_app(app)
    if close_result == "unsupported":
        return f"I can open {app['close_name']}, but closing it is not wired up yet."
    if close_result:
        return f"Closed {app['close_name']}."
    return f"I could not find {app['close_name']} running right now."