import os
from datetime import datetime
from storage import init_db, store_info, retrieve_info, save_message, load_recent_history, clear_conversation_logs
import ollama


class KoraBrain:
    def __init__(self):
        init_db()
        self.model_name = "llama3.1:8b"
        self.max_history = 40  # Messages kept in RAM window (40 = 20 exchanges)

        self.system_instruction = (
            "You are Kora, a highly capable, polite, and beautiful AI assistant. "
            "You converse naturally like a human. You keep your responses concise, precise, "
            "and conversational. Do not use asterisks or formatting because your output will be spoken aloud. "
            "You have access to a memory of past conversations with the user, so refer to them naturally "
            "when relevant — for example, 'As we discussed before...' or 'You mentioned last time that...'"
        )

        # ── Load past conversation from the database on startup ──
        self.conversation_history = load_recent_history(limit=self.max_history)

        if self.conversation_history:
            print(f"[KORA BRAIN] Loaded {len(self.conversation_history)} messages from past sessions.")
        else:
            print("[KORA BRAIN] No past conversation found. Starting fresh.")

    def learn(self, text):
        """Store a fact into long-term memory."""
        store_info("memory", text)

    def generate_reply(self, user_input):
        text = user_input.lower()

        # Handle time instantly without hitting the LLM
        if "time" in text and ("what" in text or "current" in text):
            reply = f"The current time is {datetime.now().strftime('%I:%M %p')}."
            # Still log it so the conversation record is complete
            save_message("user", user_input)
            save_message("assistant", reply)
            return reply

        # ── Long-term memory context retrieval ──
        words = text.split()
        context_items = []
        for word in words:
            if len(word) > 4:
                results = retrieve_info(word)
                if results:
                    context_items.extend(results)

        context_string = ", ".join(list(set(context_items))[:5])

        # Build the user message — inject memory context if found
        if context_string:
            full_user_prompt = f"[Relevant memory: {context_string}]\n\nUser says: {user_input}"
        else:
            full_user_prompt = user_input

        # ── Add to in-RAM history ──
        self.conversation_history.append({'role': 'user', 'content': full_user_prompt})

        # Slide the window if needed
        if len(self.conversation_history) > self.max_history:
            self.conversation_history = self.conversation_history[-self.max_history:]

        try:
            response = ollama.chat(
                model=self.model_name,
                messages=[
                    {'role': 'system', 'content': self.system_instruction},
                    *self.conversation_history
                ]
            )

            reply = response['message']['content'].strip()

            # ── Add Kora's reply to RAM history ──
            self.conversation_history.append({'role': 'assistant', 'content': reply})

            # ── Persist BOTH messages to the database ──
            save_message("user", full_user_prompt)
            save_message("assistant", reply)

            return reply

        except Exception as e:
            print(f"[Kora Brain Error]: {e}")
            return "I am having trouble connecting to my local Ollama server. Please make sure Ollama is running."

    def reset_conversation(self):
        """
        Clear the in-RAM history AND the database log.
        Long-term memories (the 'memories' table) are preserved.
        """
        self.conversation_history = []
        clear_conversation_logs()
        print("[KORA BRAIN] Conversation history cleared.")
