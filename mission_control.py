import json
import re
import ollama
from search_engine import search_online
from url_summarizer import _fetch_text
from file_ops import write_to_file
from settings import get_setting
from code_runner import handle_code_command
from plugin_architect import handle_architect_command

MISSION_PATTERN = re.compile(r"^(?:mission|task|complex task|orchestrate|plan)\s+(.+)$", re.I)

class MissionControl:
    def __init__(self):
        self.results = {}

    def is_mission_request(self, text):
        normalized = " ".join(str(text).strip().split())
        return bool(MISSION_PATTERN.match(normalized))

    def _generate_plan(self, goal):
        model = get_setting("model_name", "llama3.1:8b")
        prompt = f"""
You are the Kora Mission Planner. Break down the user's goal into a sequence of steps.
Goal: "{goal}"

Available operations (ops):
- SEARCH: input="query", store_as="key"
- SCRAPE: input="url", store_as="key"
- SUMMARIZE: input="text", store_as="key"
- WRITE_FILE: input={{"path": "file.txt", "content": "text"}}, store_as="key"
- RUN_CODE: input="python_code", store_as="key"
- CREATE_PLUGIN: input="plugin_objective", store_as="key"
- SPEAK: input="message"

Rules:
1. Output ONLY a valid JSON array of steps. No commentary.
2. Steps can reference previous results using $key.
3. For search results, use $key.results.0.link for the top link.
4. Keep the plan efficient (max 6 steps).

Example:
[
  {{"op": "SEARCH", "input": "AI news today", "store_as": "news"}},
  {{"op": "SCRAPE", "input": "$news.results.0.link", "store_as": "article"}},
  {{"op": "SUMMARIZE", "input": "$article", "store_as": "summary"}},
  {{"op": "WRITE_FILE", "input": {{"path": "news.txt", "content": "$summary"}}, "store_as": "f"}},
  {{"op": "SPEAK", "input": "I have summarized the top article for you."}}
]
"""
        try:
            print(f"[MISSION] Planning for: {goal}")
            r = ollama.chat(model=model, messages=[{"role": "user", "content": prompt}])
            content = r["message"]["content"].strip()
            
            # Extract JSON from potential code blocks
            match = re.search(r"\[.*\]", content, re.S)
            if match:
                return json.loads(match.group(0))
            return json.loads(content)
        except Exception as e:
            print(f"[MISSION PLAN ERROR] {e}")
            return None

    def _resolve_input(self, val, results):
        if isinstance(val, dict):
            return {k: self._resolve_input(v, results) for k, v in val.items()}
        
        if not isinstance(val, str) or "$" not in val:
            return val
        
        # Regex to find $key tokens and resolve them
        def repl(match):
            path = match.group(0).lstrip("$")
            parts = path.split(".")
            key = parts[0]
            if key in results:
                data = results[key]
                for part in parts[1:]:
                    try:
                        if isinstance(data, list) and part.isdigit():
                            data = data[int(part)]
                        elif isinstance(data, dict):
                            data = data.get(part, f"${path}")
                        else:
                            return f"${path}"
                    except Exception:
                        return f"${path}"
                return str(data)
            return f"${path}"

        return re.sub(r"\$[a-zA-Z0-9_.]+", repl, val)

    def execute_mission(self, text):
        match = MISSION_PATTERN.match(text.strip())
        if not match:
            return None
        
        goal = match.group(1).strip()
        plan = self._generate_plan(goal)
        if not plan:
            return {"action": "mission_error", "reply": "I couldn't formulate a plan for that mission."}
        
        self.results = {}
        replies = []
        model = get_setting("model_name", "llama3.1:8b")

        for i, step in enumerate(plan):
            op = step.get("op")
            raw_inp = step.get("input")
            store_as = step.get("store_as")
            
            inp = self._resolve_input(raw_inp, self.results)
            print(f"[MISSION STEP {i}] {op} -> {str(inp)[:100]}...")

            res = None
            try:
                if op == "SEARCH":
                    res = search_online(inp)
                    replies.append(f"Searched for {inp}.")
                elif op == "SCRAPE":
                    res = _fetch_text(inp)
                    if res:
                        replies.append(f"Fetched content from {inp[:40]}...")
                    else:
                        res = "Could not fetch content."
                elif op == "SUMMARIZE":
                    r = ollama.generate(model=model, prompt=f"Summarize concisely:\n\n{inp[:3000]}")
                    res = r["response"].strip()
                    replies.append("Created a summary.")
                elif op == "WRITE_FILE":
                    path = inp.get("path")
                    content = inp.get("content")
                    if write_to_file(path, content):
                        res = f"Saved to {path}"
                        replies.append(f"Saved the file to {path}.")
                    else:
                        res = "Failed to write file."
                elif op == "RUN_CODE":
                    code_res = handle_code_command(inp)
                    res = code_res.get("reply", "Code ran.")
                    replies.append(f"Executed code. Result: {res[:100]}...")
                elif op == "CREATE_PLUGIN":
                    arch_res = handle_architect_command(f"create plugin for {inp}")
                    res = arch_res.get("reply", "Plugin created.")
                    replies.append(f"Built a new tool: {res[:100]}...")
                elif op == "SPEAK":
                    replies.append(inp)
                    res = inp
                
                if store_as:
                    self.results[store_as] = res
            except Exception as e:
                print(f"[STEP ERROR] {e}")
                replies.append(f"(Step {i} failed: {e})")

        return {
            "action": "mission_complete",
            "reply": " ".join(replies)
        }
