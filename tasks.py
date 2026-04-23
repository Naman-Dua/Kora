import re
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from storage import (
    clear_scheduled_items,
    delete_scheduled_items,
    load_scheduled_items,
    save_scheduled_item,
)

RELATIVE_TIME_PATTERN = re.compile(
    r"\b(?:in|for|after)\s+(\d+)\s*(seconds?|secs?|minutes?|mins?|hours?|hrs?)\b",
    re.IGNORECASE,
)
ABSOLUTE_TIME_PATTERN = re.compile(
    r"\b(?:(tomorrow)\s+)?at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b",
    re.IGNORECASE,
)
LIST_PATTERN = re.compile(r"\b(list|show|what)\b.*\b(reminders|timers)\b", re.IGNORECASE)
CANCEL_TODAY_PATTERN = re.compile(r"\b(reminders|timers)\b.*\b(today)\b", re.IGNORECASE)
CANCEL_ALL_PATTERN = re.compile(
    r"(?:\b(cancel|clear|remove|delete)\b.*\b(all )?(reminders|timers)\b)|(?:\breminders?\s+off\b)",
    re.IGNORECASE,
)
TIMER_PATTERN = re.compile(r"\b(timer)\b", re.IGNORECASE)
REMINDER_PATTERN = re.compile(r"\b(remind me|set a reminder|reminder)\b", re.IGNORECASE)
LEADING_CONNECTOR_PATTERN = re.compile(r"^(to|about|that|for)\s+", re.IGNORECASE)
LEADING_ARTICLE_PATTERN = re.compile(r"^(a|an|the)\s+", re.IGNORECASE)
EMPTY_REMINDER_TASK_PATTERN = re.compile(r"^(?:set|set up|setup|make|create)\s*$", re.IGNORECASE)

UNIT_SECONDS = {
    "second": 1,
    "seconds": 1,
    "sec": 1,
    "secs": 1,
    "minute": 60,
    "minutes": 60,
    "min": 60,
    "mins": 60,
    "hour": 3600,
    "hours": 3600,
    "hr": 3600,
    "hrs": 3600,
}


@dataclass
class ScheduledItem:
    id: int
    kind: str
    task: str
    due_at: datetime
    created_at: datetime = field(default_factory=datetime.now)

    def due_phrase(self):
        return self.due_at.strftime("%I:%M %p on %A").lstrip("0")

    def trigger_message(self):
        if self.kind == "timer":
            return f"Timer complete. {self.task}"
        if self.task == "something important":
            return "Reminder time."
        return f"Reminder: {self.task}"


class ReminderManager:
    def __init__(self):
        self._lock = threading.Lock()
        self._items = []
        self._next_id = 1
        self._restore()

    def _restore(self):
        restored = []
        max_id = 0
        for row in load_scheduled_items():
            try:
                item = ScheduledItem(
                    id=int(row["id"]),
                    kind=row["kind"],
                    task=row["task"],
                    due_at=datetime.fromisoformat(row["due_at"]),
                    created_at=datetime.fromisoformat(row["created_at"]),
                )
            except Exception:
                continue
            restored.append(item)
            max_id = max(max_id, item.id)

        self._items = sorted(restored, key=lambda reminder: reminder.due_at)
        self._next_id = max_id + 1 if max_id else 1

    def schedule(self, kind, task, due_at):
        with self._lock:
            item = ScheduledItem(
                id=self._next_id,
                kind=kind,
                task=task,
                due_at=due_at,
            )
            self._next_id += 1
            self._items.append(item)
            self._items.sort(key=lambda reminder: reminder.due_at)
            save_scheduled_item(
                item.id,
                item.kind,
                item.task,
                item.due_at.isoformat(),
                item.created_at.isoformat(),
            )
            return item

    def pop_due(self, now=None):
        now = now or datetime.now()
        with self._lock:
            due_items = [item for item in self._items if item.due_at <= now]
            self._items = [item for item in self._items if item.due_at > now]
            delete_scheduled_items(item.id for item in due_items)
            return due_items

    def describe(self, now=None):
        now = now or datetime.now()
        with self._lock:
            if not self._items:
                return "You have no active reminders or timers."

            phrases = []
            for item in self._items[:5]:
                remaining = item.due_at - now
                if remaining.total_seconds() < 0:
                    continue
                phrases.append(
                    f"{item.kind} for {item.task} at {item.due_at.strftime('%I:%M %p').lstrip('0')}"
                )

            if not phrases:
                return "You have no active reminders or timers."
            return "Active reminders: " + "; ".join(phrases) + "."

    def describe_today(self, now=None):
        now = now or datetime.now()
        with self._lock:
            todays_items = [
                item for item in self._items
                if item.due_at.date() == now.date() and item.due_at >= now
            ]
            if not todays_items:
                return "You have no reminders or timers left for today."

            phrases = [
                f"{item.kind} for {item.task} at {item.due_at.strftime('%I:%M %p').lstrip('0')}"
                for item in todays_items[:5]
            ]
            return "For today: " + "; ".join(phrases) + "."

    def cancel_all(self):
        with self._lock:
            count = len(self._items)
            self._items.clear()
            clear_scheduled_items()
            return count


def _cleanup_task_text(text):
    cleaned = re.sub(r"\s+", " ", text).strip(" ,.-")
    cleaned = LEADING_CONNECTOR_PATTERN.sub("", cleaned).strip(" ,.-")
    cleaned = LEADING_ARTICLE_PATTERN.sub("", cleaned).strip(" ,.-")
    cleaned = LEADING_CONNECTOR_PATTERN.sub("", cleaned).strip(" ,.-")
    if EMPTY_REMINDER_TASK_PATTERN.fullmatch(cleaned):
        cleaned = ""
    if cleaned.lower() in {"a", "an", "the"}:
        cleaned = ""
    return cleaned or "something important"


def _parse_relative_time(text, now):
    match = RELATIVE_TIME_PATTERN.search(text)
    if not match:
        return None, None

    amount = int(match.group(1))
    unit = match.group(2).lower()
    if unit.endswith("."):
        unit = unit[:-1]

    seconds = UNIT_SECONDS.get(unit)
    if not seconds:
        return None, None

    due_at = now + timedelta(seconds=amount * seconds)
    return due_at, match.group(0)


def _parse_absolute_time(text, now):
    match = ABSOLUTE_TIME_PATTERN.search(text)
    if not match:
        return None, None

    is_tomorrow = bool(match.group(1))
    hour = int(match.group(2))
    minute = int(match.group(3) or 0)
    meridiem = match.group(4).lower()

    if hour == 12:
        hour = 0
    if meridiem == "pm":
        hour += 12

    due_at = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if is_tomorrow or due_at <= now:
        due_at += timedelta(days=1)

    return due_at, match.group(0)


def _build_schedule_reply(kind, task, due_at, now):
    if kind == "timer":
        delta = due_at - now
        total_seconds = max(0, int(delta.total_seconds()))
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)

        parts = []
        if hours:
            parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
        if minutes:
            parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
        if seconds and not hours:
            parts.append(f"{seconds} second{'s' if seconds != 1 else ''}")
        if not parts:
            parts.append("0 seconds")

        if len(parts) == 1:
            span = parts[0]
        elif len(parts) == 2:
            span = f"{parts[0]} and {parts[1]}"
        else:
            span = ", ".join(parts[:-1]) + f", and {parts[-1]}"
        return f"Timer set for {span}. I will alert you at {due_at.strftime('%I:%M %p').lstrip('0')}."

    if task == "something important":
        return f"Reminder set for {due_at.strftime('%I:%M %p').lstrip('0')}."
    return f"Reminder set for {due_at.strftime('%I:%M %p').lstrip('0')} to {task}."


def check_for_tasks(text, reminder_manager, now=None):
    """
    Parse reminder and timer commands into concrete scheduler actions.
    Returns a dict describing the action to take, or None when the text
    is not a reminder/timer request.
    """
    now = now or datetime.now()
    normalized = " ".join(text.lower().strip().split())

    if LIST_PATTERN.search(normalized):
        if CANCEL_TODAY_PATTERN.search(normalized):
            return {
                "action": "list_today",
                "reply": reminder_manager.describe_today(now),
            }
        return {
            "action": "list",
            "reply": reminder_manager.describe(now),
        }

    if "today" in normalized and ("reminder" in normalized or "timer" in normalized):
        return {
            "action": "list_today",
            "reply": reminder_manager.describe_today(now),
        }

    if CANCEL_ALL_PATTERN.search(normalized):
        removed = reminder_manager.cancel_all()
        if removed:
            return {
                "action": "cancel_all",
                "reply": f"Cleared {removed} active reminder{'s' if removed != 1 else ''}.",
            }
        return {
            "action": "cancel_all",
            "reply": "There were no active reminders to clear.",
        }

    kind = None
    if TIMER_PATTERN.search(normalized):
        kind = "timer"
    elif REMINDER_PATTERN.search(normalized):
        kind = "reminder"
    else:
        return None

    due_at, matched_time = _parse_relative_time(normalized, now)
    if due_at is None and kind == "reminder":
        due_at, matched_time = _parse_absolute_time(normalized, now)

    if due_at is None:
        if kind == "timer":
            return {
                "action": "invalid",
                "reply": "Tell me how long to run the timer, like set a timer for 10 minutes.",
            }
        return {
            "action": "invalid",
            "reply": "Tell me when to remind you, like remind me in 30 minutes or remind me at 5 PM.",
        }

    task_text = normalized
    if kind == "timer":
        task_text = re.sub(r"\b(set|start|run)\b", "", task_text)
        task_text = re.sub(r"\btimer\b", "", task_text)
        if matched_time:
            task_text = task_text.replace(matched_time, "")
        cleaned_task = _cleanup_task_text(task_text)
        task = cleaned_task if cleaned_task != "something important" else "Your timer is done."
    else:
        task_text = re.sub(
            r"\bset up a reminder\b|\bset up reminder\b|\bset reminder\b|\bset a reminder\b|\bremind me\b|\breminder\b",
            "",
            task_text,
        )
        if matched_time:
            task_text = task_text.replace(matched_time, "")
        task = _cleanup_task_text(task_text)

    if kind == "timer" and task == "something important":
        task = "Your timer is done."

    item = reminder_manager.schedule(kind, task, due_at)
    return {
        "action": "schedule",
        "item": item,
        "reply": _build_schedule_reply(kind, task, due_at, now),
    }
