from datetime import datetime

import ollama

from settings import get_setting
from storage import (
    clear_conversation_logs,
    init_db,
    load_recent_history,
    retrieve_info,
    save_message,
    store_info,
)
from task_memory import get_active_task_context
from screen_analysis import is_screen_request, capture_screen, get_available_vision_model
import os
class KoraBrain:
    def __init__(self):
        init_db()
        self.model_name = get_setting("model_name", "llama3.1:8b")
        self.max_history = 40

        self.system_instruction = (
            "You are Kora, a highly capable, polite, and beautiful AI assistant. "
            "You converse naturally like a human. You keep your responses concise, precise, "
            "and conversational. Do not use asterisks or formatting because your output will be spoken aloud. "
            "You have access to a memory of past conversations with the user and a list of active tasks. "
            "Use both when relevant, but stay direct."
        )

        self.conversation_history = load_recent_history(limit=self.max_history)
        if self.conversation_history:
            print(f"[KORA BRAIN] Loaded {len(self.conversation_history)} messages from past sessions.")
        else:
            print("[KORA BRAIN] No past conversation found. Starting fresh.")

    def learn(self, text):
        from nlp_memory import extract_facts
        facts = extract_facts(text)
        for fact in facts:
            store_info("memory", fact)
            print(f"[KORA LEARNED] {fact}")

    def generate_reply(self, user_input):
        text = user_input.lower()

        if "time" in text and ("what" in text or "current" in text):
            reply = f"The current time is {datetime.now().strftime('%I:%M %p')}."
            save_message("user", user_input)
            save_message("assistant", reply)
            return reply

        context_items = retrieve_info(text)
        context_string = " | ".join(context_items[:5])
        active_tasks = get_active_task_context()
        prompt_context = []
        if context_string:
            prompt_context.append(f"Relevant memory: {context_string}")
        if active_tasks:
            prompt_context.append(f"Active tasks: {active_tasks}")

        if prompt_context:
            full_user_prompt = f"[{' | '.join(prompt_context)}]\n\nUser says: {user_input}"
        else:
            full_user_prompt = user_input

        self.conversation_history.append({"role": "user", "content": full_user_prompt})
        if len(self.conversation_history) > self.max_history:
            self.conversation_history = self.conversation_history[-self.max_history:]

        screenshot_path = None
        model_to_use = self.model_name

        if is_screen_request(text):
            vision_model = get_available_vision_model()
            if vision_model:
                try:
                    screenshot_path = capture_screen()
                    self.conversation_history[-1]["images"] = [screenshot_path]
                    model_to_use = vision_model
                except Exception as e:
                    print(f"[Vision Error]: {e}")
            else:
                self.conversation_history.pop() # remove the user prompt since we abort
                return "I couldn't find a vision model to look at your screen. Please install llama3.2-vision."

        try:
            response = ollama.chat(
                model=model_to_use,
                messages=[
                    {"role": "system", "content": self.system_instruction},
                    *self.conversation_history,
                ],
            )

            reply = response["message"]["content"].strip()
            self.conversation_history.append({"role": "assistant", "content": reply})
            save_message("user", full_user_prompt)
            save_message("assistant", reply)
            
            if screenshot_path and os.path.exists(screenshot_path):
                os.remove(screenshot_path)
                
            return reply
        except Exception as exc:
            print(f"[Kora Brain Error]: {exc}")
            return "I am having trouble connecting to my local Ollama server. Please make sure Ollama is running."

    def reset_conversation(self):
        self.conversation_history = []
        clear_conversation_logs()
        print("[KORA BRAIN] Conversation history cleared.")
