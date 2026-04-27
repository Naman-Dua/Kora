import os
import json
import ollama
from search_engine import search_online

class SelfHealer:
    def __init__(self, model_name="llama3.1:8b"):
        self.model_name = model_name

    def diagnose_failure(self, failure_item, user_query):
        """
        Takes a failure dict: {"request": ..., "error": ...}
        and tries to suggest a fix.
        """
        request = failure_item.get("request", {})
        error = failure_item.get("error", "Unknown error")
        kind = request.get("kind")
        action = request.get("action")
        label = request.get("label")

        # If the error is cryptic, try searching for it
        search_context = ""
        if len(error) > 10 and not any(kw in error.lower() for kw in ["not found", "denied", "invalid"]):
            try:
                results = search_online(f"fix windows error: {error}")
                if results:
                    search_context = f"\nWeb search results for this error: {results[:500]}"
            except:
                pass

        prompt = (
            f"You are the 'Self-Healing' module of Jarvis (Kora). "
            f"The user tried to: '{user_query}'\n"
            f"Specifically, I failed to {action} {kind} '{label}'.\n"
            f"System Error: {error}\n"
            f"{search_context}\n"
            "Analyze the failure. If it's a 'file not found' or 'path' issue, suggest checking common locations "
            "or searching for the executable. If it's a permission issue, mention that. "
            "If the web search provided a solution, summarize it. "
            "IMPORTANT: If a file is missing, Kora should offer to search the system for it. "
            "Propose a specific correction that Kora can perform or ask the user for more info. "
            "Keep it very brief, conversational, and direct. Do not use markdown."
        )

        try:
            response = ollama.chat(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}]
            )
            diagnosis = response["message"]["content"].strip()
            return diagnosis
        except Exception as e:
            return f"I encountered an error while trying to self-heal: {str(e)}"

    def attempt_autonomous_fix(self, failure_item):
        """
        Actually tries to fix things (e.g., searching for a missing exe).
        Returns a suggested command or a status.
        """
        request = failure_item.get("request", {})
        error = failure_item.get("error", "").lower()
        
        if "no valid path" in error or "not found" in error:
            # Try a quick search for common locations or web search for default install paths
            app_name = request.get("label", "")
            search_query = f"default installation path for {app_name} on windows"
            # search_results = search_online(search_query) # Could use this
            
            return f"I couldn't find {app_name} where I expected it. Should I try searching your C drive for it?"
            
        return None

def handle_self_healing(failures, user_query, brain):
    """Entry point for self-healing logic."""
    healer = SelfHealer(model_name=brain.model_name)
    suggestions = []
    
    for failure in failures:
        diagnosis = healer.diagnose_failure(failure, user_query)
        suggestions.append(diagnosis)
    
    return " ".join(suggestions)
