

import ollama
import json
import os

MEMORY_FILE = "user_memory.json"

def get_profile():
    if not os.path.exists(MEMORY_FILE):
        default = {"master_name": "Naman", "habits": [], "learned_facts": [], "current_tasks": []}
        with open(MEMORY_FILE, 'w') as f:
            json.dump(default, f, indent=4)
        return default
    with open(MEMORY_FILE, 'r') as f:
        return json.load(f)

def update_memory_autonomously(user_input):
    """Jarvis analyzes the conversation to learn about you without being told."""
    profile = get_profile()
    
    # We ask the LLM to extract new information from the chat
    learning_prompt = f"""
    Current Profile: {json.dumps(profile)}
    New Input from Master: "{user_input}"
    
    Task: If there is a new fact, task, or habit in the input, update the JSON. 
    If nothing new, return the original JSON. 
    Return ONLY the raw JSON. No conversational text.
    """
    
    try:
        response = ollama.chat(model='llama3.1:8b', messages=[{'role': 'user', 'content': learning_prompt}])
        content = response['message']['content']
        # Extracting JSON if LLM adds markdown backticks
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        
        updated_data = json.loads(content)
        with open(MEMORY_FILE, 'w') as f:
            json.dump(updated_data, f, indent=4)
    except:
        pass # Silently fail if LLM output isn't perfect JSON

def ask_jarvis(prompt, system_status):
    profile = get_profile()
    
    system_instructions = f"""
    You are JARVIS. Your Master is {profile['master_name']}. 
    Master's Profile: {json.dumps(profile)}
    System Status: {system_status}
    
    Role: You are an autonomous observer. You know what the Master is doing. 
    Be loyal, sophisticated, and proactive. Use "sir" naturally.
    """
    
    response = ollama.chat(model='llama3.1:8b', messages=[
        {'role': 'system', 'content': system_instructions},
        {'role': 'user', 'content': prompt},
    ])
    
    # Learn from the interaction
    update_memory_autonomously(prompt)
    
    return response['message']['content']