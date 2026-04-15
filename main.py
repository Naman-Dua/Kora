from ears import listen
from voice import speak
from search_engine import search_online
from jarvis_engine import JarvisBrain

# Initialize your custom brain
brain = JarvisBrain()

def run_jarvis():
    speak("Systems online. I am connected to the global grid.")
    
    while True:
        try:
            # 1. Listen for voice command
            user_input = listen()
            if not user_input or len(user_input) < 3:
                continue
            
            print(f"Master: {user_input}")
            user_cmd = user_input.lower()

            # 2. TRIGGER: Search Online
            if "search" in user_cmd:
                # Remove the word 'search' to get the clean query
                query = user_cmd.replace("search", "").strip()
                speak(f"Scanning the web for {query}...")
                
                # Fetch online data
                web_result = search_online(query)
                
                # JARVIS learns the new information into his JSON memory
                brain.learn(f"Internet search for {query}: {web_result}")
                
                speak(f"Found the following: {web_result}")

            # 3. Shutdown command
            elif "go to sleep" in user_cmd or "exit" in user_cmd:
                speak("Understood. Powering down systems. Goodbye, sir.")
                break

            # 4. Standard Learning (Conversation)
            else:
                brain.learn(user_input)
                # Recalls if he knows something about what you said
                context = brain.recall(user_input.split()[-1])
                print(f"Log: {context}")
                speak("Information noted.")

        except Exception as e:
            print(f"Main Loop Error: {e}")
            continue

if __name__ == "__main__":
    run_jarvis()