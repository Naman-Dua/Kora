import sqlite3

DB_PATH = 'aura_memory.db'

def init_db():
    """Initialize the database and ensure the unified schema is in place.
    Safe to call multiple times — uses CREATE IF NOT EXISTS and ALTER TABLE migration.
    """
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS memories
                        (id       INTEGER PRIMARY KEY,
                         category TEXT,
                         content  TEXT,
                         timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
        # Migration: add 'category' column for databases created by the old brain.py schema.
        try:
            conn.execute("ALTER TABLE memories ADD COLUMN category TEXT")
        except sqlite3.OperationalError:
            pass  # Column already exists — nothing to do.
        conn.commit()

def store_info(category, content):
    """Insert a memory entry, skipping duplicates (same content already stored)."""
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        # Bug fix: deduplicate — don't store the same content twice.
        cur.execute("SELECT id FROM memories WHERE content = ?", (content,))
        if not cur.fetchone():
            conn.execute(
                "INSERT INTO memories (category, content) VALUES (?, ?)",
                (category, content)
            )
            conn.commit()

def retrieve_info(keyword):
    """Return all memory contents that contain the given keyword."""
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT content FROM memories WHERE content LIKE ?",
            ('%' + keyword + '%',)
        )
        return [r[0] for r in cur.fetchall()]

# Bug fix (Bug 12): Do NOT call init_db() here at module level.
# Calling it on import is a side effect that breaks testing and runs
# even in scripts that never need the DB. Call init_db() explicitly
# at app startup (brain.py JarvisBrain.__init__ handles this).