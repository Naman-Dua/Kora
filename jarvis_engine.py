import json
import os

class JarvisBrain:
    def __init__(self):
        self.file = "jarvis_knowledge.json"
        if not os.path.exists(self.file):
            with open(self.file, 'w') as f: json.dump({"entities": {}}, f)

    def learn(self, text):
        with open(self.file, 'r') as f: data = json.load(f)
        words = text.lower().split()
        for word in words:
            if len(word) > 4:
                data["entities"][word] = data["entities"].get(word, 0) + 1
        with open(self.file, 'w') as f: json.dump(data, f, indent=4)

    def recall(self, query):
        with open(self.file, 'r') as f: data = json.load(f)
        return "I have a record of that" if query.lower() in data["entities"] else "That is new to me"