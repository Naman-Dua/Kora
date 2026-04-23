import re

from storage import load_task_memory, update_task_status, upsert_task_memory

FOCUS_PATTERNS = [
    re.compile(r"^(?:focus on|work on|working on|set project to|remember that we're working on)\s+(.+)$", re.IGNORECASE),
    re.compile(r"^(?:track task|track project)\s+(.+)$", re.IGNORECASE),
]
DONE_PATTERNS = [
    re.compile(r"^(?:done with|finished|complete|completed|close out)\s+(.+)$", re.IGNORECASE),
]
LIST_PATTERNS = [
    re.compile(r"^(?:what are we working on|what am i working on|current focus|list tasks|list projects|show tasks)$", re.IGNORECASE),
]


def _normalize_title(text):
    return " ".join(str(text).strip(" .").split())


def _format_tasks(tasks):
    if not tasks:
        return "There is no active task memory yet."
    snippets = []
    for task in tasks[:5]:
        note = f" ({task['notes']})" if task["notes"] else ""
        snippets.append(f"{task['title']}{note}")
    return "Current focus: " + "; ".join(snippets) + "."


def get_active_task_context(limit=3):
    tasks = load_task_memory(status="active", limit=limit)
    if not tasks:
        return ""
    return "; ".join(task["title"] for task in tasks if task["title"])


def handle_task_memory_command(text):
    normalized = " ".join(str(text).strip().split())

    for pattern in LIST_PATTERNS:
        if pattern.match(normalized):
            return {"action": "list_focus", "reply": _format_tasks(load_task_memory(status="active"))}

    for pattern in FOCUS_PATTERNS:
        match = pattern.match(normalized)
        if match:
            title = _normalize_title(match.group(1))
            if not title:
                break
            upsert_task_memory(title, status="active")
            return {
                "action": "set_focus",
                "title": title,
                "reply": f"Locked in. I'll treat {title} as an active focus.",
            }

    for pattern in DONE_PATTERNS:
        match = pattern.match(normalized)
        if match:
            title = _normalize_title(match.group(1))
            if not title:
                break
            update_task_status(title, "completed")
            return {
                "action": "complete_focus",
                "title": title,
                "reply": f"Marked {title} as completed.",
            }

    return None
