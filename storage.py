import sqlite3

def init_db():
    conn = sqlite3.connect('jarvis_memory.db')
    cursor = conn.cursor()
    # Create tables for different types of "things"
    cursor.execute('''CREATE TABLE IF NOT EXISTS memories 
                      (id INTEGER PRIMARY KEY, category TEXT, content TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()

def store_info(category, content):
    conn = sqlite3.connect('jarvis_memory.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO memories (category, content) VALUES (?, ?)", (category, content))
    conn.commit()
    conn.close()

def retrieve_info(keyword):
    conn = sqlite3.connect('jarvis_memory.db')
    cursor = conn.cursor()
    # Search for anything related to the keyword
    cursor.execute("SELECT content FROM memories WHERE content LIKE ?", ('%' + keyword + '%',))
    results = cursor.fetchall()
    conn.close()
    return [r[0] for r in results]

# Initialize on first run
init_db()