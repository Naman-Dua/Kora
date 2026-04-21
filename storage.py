import sqlite3

DB_PATH = 'kora_memory.db'


def init_db():
    """Initialize all tables. Safe to call multiple times."""
    with sqlite3.connect(DB_PATH) as conn:

        # --- Long-term facts/memory ---
        conn.execute('''
            CREATE TABLE IF NOT EXISTS memories (
                id        INTEGER PRIMARY KEY,
                category  TEXT,
                content   TEXT UNIQUE,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # --- Full conversation log (persists across restarts) ---
        conn.execute('''
            CREATE TABLE IF NOT EXISTS conversation_logs (
                id        INTEGER PRIMARY KEY,
                role      TEXT NOT NULL,
                content   TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Index for fast keyword search on memories
        conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_memory_content
            ON memories (content)
        ''')

        conn.commit()


# ──────────────────────────────────────────────
#  MEMORY  (long-term facts)
# ──────────────────────────────────────────────

def store_info(category, content):
    """Insert a memory entry, skipping exact duplicates."""
    with sqlite3.connect(DB_PATH) as conn:
        try:
            conn.execute(
                "INSERT INTO memories (category, content) VALUES (?, ?)",
                (category, content)
            )
            conn.commit()
        except sqlite3.IntegrityError:
            pass  # UNIQUE constraint — already stored


def retrieve_info(keyword):
    """Return memory contents that contain the keyword."""
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT content FROM memories WHERE content LIKE ? LIMIT 10",
            ('%' + keyword + '%',)
        )
        return [r[0] for r in cur.fetchall()]


# ──────────────────────────────────────────────
#  CONVERSATION LOGS  (persistent chat history)
# ──────────────────────────────────────────────

def save_message(role, content):
    """Append a single message (user or assistant) to the persistent log."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO conversation_logs (role, content) VALUES (?, ?)",
            (role, content)
        )
        conn.commit()


def load_recent_history(limit=40):
    """
    Load the last `limit` messages from the log as a list of
    {'role': ..., 'content': ...} dicts — ready for ollama.chat().
    """
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute(
            '''
            SELECT role, content FROM conversation_logs
            ORDER BY id DESC LIMIT ?
            ''',
            (limit,)
        )
        rows = cur.fetchall()

    # Reverse so oldest is first (correct chronological order for the LLM)
    return [{'role': row[0], 'content': row[1]} for row in reversed(rows)]


def load_all_logs():
    """
    Return every log entry as (timestamp, role, content) tuples.
    Used by the GUI to populate the log panel on startup.
    """
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT timestamp, role, content FROM conversation_logs ORDER BY id ASC"
        )
        return cur.fetchall()


def clear_conversation_logs():
    """Wipe the conversation history (keeps long-term memories intact)."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM conversation_logs")
        conn.commit()
