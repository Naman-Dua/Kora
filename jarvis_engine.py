import json
import os

class JarvisBrain:
    def __init__(self):
        self.memory_file = "jarvis_knowledge.json"
        self.knowledge = self.load_knowledge()

    def load_knowledge(self):
        if os.path.exists(self.memory_file):
            with open(self.memory_file, 'r') as f:
                return json.load(f)
        return {"entities": {}, "connections": []}

    def learn(self, text):
        """Simple NLP to extract and connect information"""
        words = text.lower().split()
        
        # 1. Identify potential 'things' (nouns)
        # In a full build, you'd use a library like spaCy here
        important_words = [w for w in words if len(w) > 3]

        # 2. Update the Brain's internal count of what it knows
        for word in important_words:
            if word not in self.knowledge["entities"]:
                self.knowledge["entities"][word] = {"mentions": 1, "related_to": []}
            else:
                self.knowledge["entities"][word]["mentions"] += 1

        # 3. Create connections between words in the same sentence
        for i in range(len(important_words)):
            for j in range(i + 1, len(important_words)):
                connection = sorted([important_words[i], important_words[j]])
                if connection not in self.knowledge["connections"]:
                    self.knowledge["connections"].append(connection)

        self.save_knowledge()

    def save_knowledge(self):
        with open(self.memory_file, 'w') as f:
            json.dump(self.knowledge, f, indent=4)

    def recall(self, query):
        """Finds what Jarvis knows about a topic"""
        query = query.lower()
        if query in self.knowledge["entities"]:
            related = [c for c in self.knowledge["connections"] if query in c]
            return f"I know {query}. It is linked to: {related}"
        return "I haven't learned about that yet, sir."