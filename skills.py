import re

DEFAULT_SKILLS = {
    "research": {
        "description": "Search the web and summarize top findings.",
        "example": "use research skill to compare local Ollama vision models",
    },
    "vision": {
        "description": "Inspect the current screen and describe what Kora sees.",
        "example": "use vision skill to analyze my screen",
    },
    "focus": {
        "description": "Track or recall the active task we are working on.",
        "example": "use focus skill to work on TODOAPP notifications",
    },
    "automation": {
        "description": "Save or replay a reusable workflow.",
        "example": "save this workflow as morning setup",
    },
}

LIST_SKILLS_PATTERN = re.compile(r"^(?:list|show|what are)\s+skills$", re.IGNORECASE)
SKILL_COMMAND_PATTERN = re.compile(
    r"^(?:use|run)\s+([a-zA-Z0-9_-]+)\s+skill(?:\s+to)?\s+(.+)$",
    re.IGNORECASE,
)


def describe_skills():
    entries = []
    for name, skill in DEFAULT_SKILLS.items():
        entries.append(f"{name}: {skill['description']} Example: {skill['example']}.")
    return "Available skills: " + " ".join(entries)


def is_skill_list_request(text):
    return bool(LIST_SKILLS_PATTERN.match(" ".join(str(text).strip().split())))


def parse_skill_command(text):
    normalized = " ".join(str(text).strip().split())
    match = SKILL_COMMAND_PATTERN.match(normalized)
    if not match:
        return None
    skill_name = match.group(1).lower()
    payload = match.group(2).strip()
    if skill_name not in DEFAULT_SKILLS:
        return None
    return {"skill": skill_name, "payload": payload}
