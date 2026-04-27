import ollama
import re
from datetime import datetime
from storage import init_db, save_message, retrieve_info, store_info, clear_conversation_logs, load_recent_history
from task_memory import get_active_task_context
from settings import get_setting

class KoraBrain:
    def __init__(self):
        init_db()
        self.model_name = get_setting("model_name", "llama3.1:8b")
        self.max_history = 40
        self.system_instruction = (
            "You are Kora, a highly capable, polite, and beautiful AI assistant. "
            "You converse naturally like a human. You keep your responses concise, precise, "
            "and conversational. Do not use asterisks or formatting because your output will be spoken aloud. "
            "You have access to a memory of past conversations and active tasks. Use them when relevant."
        )
        self.conversation_history = load_recent_history(limit=self.max_history)

    def learn(self, text):
        from nlp_memory import extract_facts
        facts = extract_facts(text, self.model_name)
        for fact in facts:
            store_info("memory", fact)
            print(f"[KORA LEARNED] {fact}")

    def generate_reply(self, user_input):
        text = user_input.lower()
        
        # Priority check for time
        if "time" in text and ("what" in text or "current" in text):
            return f"The current time is {datetime.now().strftime('%I:%M %p')}."

        # RAG - Context Retrieval
        context_items = retrieve_info(text)
        context_string = " | ".join(context_items[:5])
        active_tasks = get_active_task_context()
        
        prompt_context = []
        if context_string:
            prompt_context.append(f"Relevant memory: {context_string}")
        if active_tasks:
            prompt_context.append(f"Active tasks: {active_tasks}")

        current_user_prompt = f"[{' | '.join(prompt_context)}]\n\nUser: {user_input}" if prompt_context else user_input

        self.conversation_history.append({"role": "user", "content": user_input})
        if len(self.conversation_history) > self.max_history:
            self.conversation_history = self.conversation_history[-self.max_history:]

        try:
            llm_messages = [
                {"role": "system", "content": self.system_instruction},
                *self.conversation_history[:-1],
                {"role": "user", "content": current_user_prompt}
            ]

            response = ollama.chat(
                model=self.model_name,
                messages=llm_messages,
            )

            reply = response["message"]["content"].strip()
            
            # 2. Analyze Sentiment & Proactive Intent (Fast secondary check)
            intent_prompt = (
                f"Analyze this user input: '{user_input}'. "
                "If the user mentions a meeting, task, or appointment with a specific time, "
                "extract it as a JSON: {'action': 'schedule', 'task': 'description', 'time': 'HH:MM'}. "
                "Otherwise respond with 'NONE'. Then, analyze the AI reply: '{reply}' "
                "and respond with exactly one word for mood: POSITIVE, NEGATIVE, URGENT, or IDLE. "
                "Format: [INTENT_JSON] | [MOOD]"
            )
            m_res = ollama.chat(model=self.model_name, messages=[{"role": "user", "content": intent_prompt}])
            raw_m = m_res["message"]["content"].strip()
            
            # Parse mood and intent
            mood = "IDLE"
            auto_intent = None
            if "|" in raw_m:
                intent_part, mood_part = raw_m.split("|", 1)
                mood = mood_part.strip().upper()
                if "{" in intent_part:
                    try:
                        # Simple extraction
                        import json
                        start = intent_part.find("{")
                        end = intent_part.rfind("}") + 1
                        auto_intent = json.loads(intent_part[start:end])
                    except: pass
            else:
                mood = raw_m.upper()

            if mood not in ["POSITIVE", "NEGATIVE", "URGENT", "IDLE"]:
                mood = "IDLE"

            self.conversation_history.append({"role": "assistant", "content": reply})
            save_message("user", user_input)
            save_message("assistant", reply)
            
            return {"text": reply, "mood": mood, "intent": auto_intent}
        except Exception as e:
            print(f"[Kora Brain Error]: {e}")
            return {"text": "I'm having trouble connecting to my local Llama model.", "mood": "NEGATIVE"}

    def reset_conversation(self):
        self.conversation_history = []
        clear_conversation_logs()
        print("[KORA BRAIN] Conversation history cleared.")
