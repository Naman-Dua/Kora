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
            "You are Kora, a highly capable and conversational AI assistant. "
            "You keep responses concise and precise. Do not use markdown or asterisks. "
            "At the VERY END of your response, you MUST include a metadata tag in this format: "
            "[MOOD: POSITIVE|NEGATIVE|URGENT|IDLE] [INTENT: JSON or NONE]. "
            "Example: 'I can help with that. [MOOD: POSITIVE] [INTENT: NONE]'"
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
            return {"text": f"The current time is {datetime.now().strftime('%I:%M %p')}.", "mood": "IDLE"}

        # RAG - Context Retrieval
        from storage import load_recent_memories
        core_memories = load_recent_memories(limit=5) # Get top 5 persistent facts
        core_facts = [m[1] for m in core_memories] if core_memories else []
        
        context_items = retrieve_info(text)
        # Avoid duplicating core facts in context items
        context_items = [i for i in context_items if i not in core_facts]
        context_string = " | ".join(context_items[:5])
        
        active_tasks = get_active_task_context()
        
        prompt_context = []
        if core_facts:
            prompt_context.append(f"Core User Facts: {' | '.join(core_facts)}")
        if context_string:
            prompt_context.append(f"Relevant Context: {context_string}")
        if active_tasks:
            prompt_context.append(f"Active tasks: {active_tasks}")

        current_user_prompt = f"[{' || '.join(prompt_context)}]\n\nUser: {user_input}" if prompt_context else user_input

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

            full_reply = response["message"]["content"].strip()
            
            # Parse mood and intent from the metadata tag
            mood = "IDLE"
            auto_intent = None
            clean_reply = full_reply
            
            # Extract [MOOD: ...]
            mood_match = re.search(r"\[MOOD:\s*(\w+)\]", full_reply, re.IGNORECASE)
            if mood_match:
                mood = mood_match.group(1).upper()
                clean_reply = clean_reply.replace(mood_match.group(0), "").strip()
                
            # Extract [INTENT: ...]
            intent_match = re.search(r"\[INTENT:\s*({.+}|NONE)\]", full_reply, re.IGNORECASE)
            if intent_match:
                intent_part = intent_match.group(1)
                clean_reply = clean_reply.replace(intent_match.group(0), "").strip()
                if intent_part.startswith("{"):
                    try:
                        import json
                        auto_intent = json.loads(intent_part)
                    except: pass

            if mood not in ["POSITIVE", "NEGATIVE", "URGENT", "IDLE"]:
                mood = "IDLE"

            self.conversation_history.append({"role": "assistant", "content": clean_reply})
            save_message("user", user_input)
            save_message("assistant", clean_reply)
            
            return {"text": clean_reply, "mood": mood, "intent": auto_intent}
        except Exception as e:
            print(f"[Kora Brain Error]: {e}")
            return {"text": "I'm having trouble connecting to my local Llama model.", "mood": "NEGATIVE"}

    def reset_conversation(self):
        self.conversation_history = []
        clear_conversation_logs()
        print("[KORA BRAIN] Conversation history cleared.")
