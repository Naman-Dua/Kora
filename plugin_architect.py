import os
import re
import ollama
from settings import get_setting
from plugin_loader import load_plugins

PLUGIN_DIR = os.path.join(os.path.dirname(__file__), "plugins")

CREATE_PLUGIN_PATTERN = re.compile(
    r"^(?:create|write|make|generate)\s+(?:a\s+)?(?:plugin|skill)\s+(?:for|that|to)\s+(.+)$",
    re.IGNORECASE
)

def is_architect_request(text):
    normalized = " ".join(str(text).strip().split())
    return bool(CREATE_PLUGIN_PATTERN.match(normalized))

def handle_architect_command(text):
    match = CREATE_PLUGIN_PATTERN.match(text.strip())
    if not match:
        return None

    objective = match.group(1).strip()
    model_name = get_setting("model_name", "llama3.1:8b")

    prompt = f"""
You are the Kora Plugin Architect. Your task is to write a Python plugin for the Kora AI assistant.
The user wants a plugin for: "{objective}"

The plugin MUST follow this exact structure:

```python
# DESCRIPTION = "Brief description of the plugin"

import re

def matches(text: str) -> bool:
    # Return True if this plugin should handle the text
    # Use regex or simple string checks
    pass

def handle_command(text: str) -> dict | None:
    # Logic to execute the command
    # Return format: {{"action": "plugin_name", "reply": "Response for Kora to speak"}}
    pass
```

Rules:
1. ONLY output the Python code. No explanations.
2. Use standard Python libraries.
3. Keep it simple and robust.
4. Ensure the `matches` function is specific to the user's request.

Write the code now.
"""

    try:
        if not os.path.exists(PLUGIN_DIR):
            os.makedirs(PLUGIN_DIR)

        print(f"[ARCHITECT] Generating plugin for: {objective}")
        response = ollama.chat(
            model=model_name,
            messages=[{"role": "user", "content": prompt}]
        )
        code = response["message"]["content"].strip()

        # Clean up the code (remove markdown backticks if present)
        code = re.sub(r"```python\s*", "", code)
        code = re.sub(r"```", "", code).strip()

        # Generate a filename
        safe_name = re.sub(r"\W+", "_", objective).lower()[:30].strip("_")
        filename = f"dynamic_{safe_name}.py"
        filepath = os.path.join(PLUGIN_DIR, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(code)

        print(f"[ARCHITECT] Saved plugin to {filepath}")
        
        # Reload plugins
        load_plugins()

        return {
            "action": "create_plugin",
            "reply": f"I've designed and installed the '{objective}' plugin for you. You can try it out now!"
        }

    except Exception as e:
        print(f"[ARCHITECT ERROR] {e}")
        return {
            "action": "architect_error",
            "reply": f"I encountered an error while designing the plugin: {e}"
        }
