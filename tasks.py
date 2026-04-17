import re

def check_for_tasks(text):
    text = text.lower()

    # Bug fix 1: Require am/pm/o'clock to avoid matching bare numbers.
    # Old pattern matched any 1-2 digit number, e.g. "call 5 people" → time="5".
    time_pattern = r"(\d{1,2}(?::\d{2})?\s*(?:am|pm|o'clock))"

    if "remind me" in text or "reminder" in text:
        times = re.findall(time_pattern, text)
        time_found = times[0] if times else "soon"

        # Bug fix 2: Use word-boundary regex substitution instead of str.replace("at", "").
        # The old approach mutilated words containing "at", e.g. "that" → "th", "water" → "wouldwer".
        task = re.sub(r'\breminder\b|\bremind\s+me\b', '', text)
        task = re.sub(r'\bat\b', '', task)
        if time_found != "soon":
            task = task.replace(time_found, "")
        task = re.sub(r'\s+', ' ', task).strip()

        return {
            "task": task if task else "something important",
            "time": time_found,
            "reply": f"Task logged, sir. Reminding you to {task} at {time_found}."
        }
    return None