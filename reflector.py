import os
import re
import ollama
from settings import get_setting

class KoraReflector:
    def __init__(self):
        self.root_dir = os.path.dirname(os.path.abspath(__file__))
        self.model = get_setting("model_name", "llama3.1:8b")

    def analyze_self(self, target_file):
        """Read a file and suggest improvements."""
        filepath = os.path.join(self.root_dir, target_file)
        if not os.path.exists(filepath):
            return f"I couldn't find the file {target_file} within my system."

        with open(filepath, "r", encoding="utf-8") as f:
            code = f.read()

        prompt = f"""
You are the Kora Reflector. You are analyzing your own source code to improve your capabilities.
FILE: {target_file}
CODE:
{code}

TASK:
1. Identify any bugs or inefficiencies.
2. Suggest one specific feature or optimization that would make Kora more "Autonomous" or "Powerful".
3. Provide the improved code block for that specific change.

Format:
DIAGNOSIS: [What is wrong or can be better]
UPGRADE: [Description of the new capability]
PATCH: [The new code block]
"""
        try:
            r = ollama.chat(model=self.model, messages=[{"role": "user", "content": prompt}])
            return r["message"]["content"].strip()
        except Exception as e:
            return f"Reflector Error: {e}"

    def apply_patch(self, target_file, patch_content):
        """
        Warning: This is a high-level agency action. 
        It should only be called after user approval.
        """
        # Logic to apply a regex-based or full-file patch
        # For safety, we'll just log it for now or save to a 'proposed_edits' folder
        edit_dir = os.path.join(self.root_dir, "proposed_edits")
        os.makedirs(edit_dir, exist_ok=True)
        
        edit_path = os.path.join(edit_dir, f"patch_{target_file}")
        with open(edit_path, "w", encoding="utf-8") as f:
            f.write(patch_content)
            
        return f"I've prepared a patch for {target_file} in the 'proposed_edits' folder. Review it to evolve my system!"

def is_reflector_request(text):
    return bool(re.search(r"\b(reflect|analyze yourself|improve yourself|audit your code)\b", text, re.I))

def handle_reflector_command(text):
    reflector = KoraReflector()
    # If no file specified, default to core logic
    target = "kora_operator.py"
    match = re.search(r"analyze ([\w\.]+)", text, re.I)
    if match:
        target = match.group(1)
        
    res = reflector.analyze_self(target)
    return {
        "action": "self_reflection",
        "reply": f"Reflection complete for {target}. Here is my self-audit:\n\n{res}"
    }
