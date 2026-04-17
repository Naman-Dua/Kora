import os
from datetime import datetime
from storage import init_db, store_info, retrieve_info
import ollama

class AuraBrain:
    def __init__(self):
        init_db()
        
        self.model_name = "gemma4:26b" # Using Gemma as requested

        self.system_instruction = (
            "You are Aura, a highly capable, polite, and beautiful AI assistant. "
            "You converse naturally like a human. You keep your responses concise, precise, "
            "and conversational. Do not use asterisks or formatting because your output will be spoken aloud."
        )

    def learn(self, text):
        """Stores a memory for future context."""
        store_info("memory", text)

    def generate_reply(self, user_input):
        text = user_input.lower()

        # Handle simple time requests immediately without API wait
        if "time" in text and ("what" in text or "current" in text):
            return f"The current time is {datetime.now().strftime('%H:%M')}."

        # Search the database for any related context based on keywords in the prompt
        words = text.split()
        context_items = []
        for word in words:
            if len(word) > 4:
                results = retrieve_info(word)
                if results:
                    context_items.extend(results)
        
        # Deduplicate context if any was found
        context_items = list(set(context_items))

        # Build the prompt
        prompt = user_input
        if context_items:
            prompt = f"Knowledge base/Context facts: {', '.join(context_items[:4])}\n\nUser says: {user_input}"
        else:
            prompt = f"User says: {user_input}"

        try:
            # Use local Ollama model
            response = ollama.generate(
                model=self.model_name,
                prompt=f"{self.system_instruction}\n\n{prompt}"
            )
            return response['response'].strip()
        except Exception as e:
            print(f"[Aura Brain Error]: {e}")
            return "I am having trouble connecting to my local Ollama server, sir. Please make sure Ollama is running."