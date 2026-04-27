import ollama
import json

def extract_facts(text, model_name="llama3.1:8b"):
    """
    Uses the local LLM to extract facts, preferences, and important memory points.
    Returns a list of extracted facts.
    """
    prompt = f"""
You are Kora's autonomous memory extraction module. Analyze the user's text and extract any long-term factual information, user preferences, states, relationships, or important details worth remembering. 
Do not extract transient commands, casual chat, or questions.

Facts to ALWAYS extract:
- User's name, age, residence, occupation, family members, or pets (e.g. "My dog's name is Rex" -> "User's dog's name is Rex").
- User's likes, dislikes, habits, and preferences (e.g. "I live in New York" -> "User lives in New York", "I like to eat pizza" -> "User likes to eat pizza").
- Long-term goals, states, or needs.

Format your output strictly as a JSON list of strings. Each string should be a clear, standalone fact about the user.
If there is nothing worth remembering (e.g. casual chat, short commands like "turn off lights", "hi"), output an empty list: []

Examples:
"My dog's name is Rex" -> ["User's dog's name is Rex"]
"I am a software engineer and I live in Austin" -> ["User is a software engineer", "User lives in Austin"]
"I love watching movies on weekends" -> ["User loves watching movies on weekends"]
"What time is it?" -> []
"Can you open Chrome?" -> []
"Turn off the lights" -> []

User text: {text}
Output JSON list ONLY:
"""
    try:
        response = ollama.generate(model=model_name, prompt=prompt)
        content = response['response'].strip()
        
        # Robust JSON extraction: Find the first '[' and the last ']'
        import re
        match = re.search(r'\[.*\]', content, re.DOTALL)
        if match:
            json_str = match.group(0)
            try:
                facts = json.loads(json_str)
                if isinstance(facts, list):
                    return [str(f) for f in facts]
            except json.JSONDecodeError:
                pass
        
        return []
    except Exception as e:
        print(f"[LLM Memory Extractor Error] {e}")
        return []

if __name__ == "__main__":
    # Test cases
    test_sentences = [
        "My favorite color is blue.",
        "My dog's name is Rex.",
        "I am a software engineer.",
        "I live in New York City.",
        "I like to eat pizza.",
        "I love watching movies on weekends.",
        "I need a new laptop.",
        "Turn off the lights."  # Should extract nothing
    ]
    for s in test_sentences:
        res = extract_facts(s)
        print(f"{s} -> {res}")
