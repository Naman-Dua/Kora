import json
import sqlite3
import hashlib
import chromadb
from datetime import datetime

DB_PATH = "kora_memory.db"

chroma_client = None
chroma_collection = None


def init_chroma():
    global chroma_client, chroma_collection
    if chroma_client is None:
        try:
            chroma_client = chromadb.PersistentClient(path="kora_chroma_db")
            chroma_collection = chroma_client.get_or_create_collection(name="kora_memories")
        except Exception as e:
            print(f"[Storage] Failed to init ChromaDB: {e}")


def _connect():
    return sqlite3.connect(DB_PATH)


def init_db():
    """Initialize all tables. Safe to call multiple times."""
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS memories (
                id        INTEGER PRIMARY KEY,
                category  TEXT,
                content   TEXT UNIQUE,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS conversation_logs (
                id        INTEGER PRIMARY KEY,
                role      TEXT NOT NULL,
                content   TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_memory_content
            ON memories (content)
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS telemetry_events (
                id          INTEGER PRIMARY KEY,
                event_name  TEXT NOT NULL,
                source      TEXT,
                value       TEXT,
                session_id  TEXT,
                timestamp   DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_telemetry_event_name
            ON telemetry_events (event_name)
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key         TEXT PRIMARY KEY,
                value       TEXT NOT NULL,
                updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS scheduled_items (
                id          INTEGER PRIMARY KEY,
                kind        TEXT NOT NULL,
                task        TEXT NOT NULL,
                due_at      TEXT NOT NULL,
                created_at  TEXT NOT NULL
            )
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_scheduled_due_at
            ON scheduled_items (due_at)
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS task_memory (
                id          INTEGER PRIMARY KEY,
                title       TEXT NOT NULL,
                notes       TEXT,
                status      TEXT NOT NULL DEFAULT 'active',
                updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_task_memory_title
            ON task_memory (title)
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS automations (
                name         TEXT PRIMARY KEY,
                automation_type TEXT NOT NULL,
                payload      TEXT NOT NULL,
                created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_run_at  DATETIME
            )
            """
        )

        conn.commit()


def store_info(category, content):
    """Insert a memory entry into both SQLite (for UI) and ChromaDB (for semantics)."""
    init_db()
    init_chroma()
    with _connect() as conn:
        try:
            conn.execute(
                "INSERT INTO memories (category, content) VALUES (?, ?)",
                (category, content),
            )
            conn.commit()
        except sqlite3.IntegrityError:
            pass

    if chroma_collection is not None:
        doc_id = hashlib.md5(content.encode('utf-8')).hexdigest()
        try:
            chroma_collection.add(
                documents=[content],
                metadatas=[{"category": category}],
                ids=[doc_id]
            )
        except Exception:
            pass


def retrieve_info(keyword):
    """Return memory contents using semantic search from ChromaDB, falling back to SQLite."""
    init_db()
    init_chroma()

    if chroma_collection is not None:
        try:
            results = chroma_collection.query(
                query_texts=[keyword],
                n_results=5
            )
            if results and results.get('documents') and results['documents'][0]:
                return results['documents'][0]
        except Exception as e:
            print(f"[Storage] ChromaDB search failed: {e}")

    # Fallback to keyword search
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT content FROM memories WHERE content LIKE ? ORDER BY id DESC LIMIT 5",
            ("%" + keyword + "%",),
        )
        return [row[0] for row in cur.fetchall()]


def load_recent_memories(limit=20):
    init_db()
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT category, content, timestamp
            FROM memories
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        )
        return cur.fetchall()


def save_message(role, content):
    """Append a single message (user or assistant) to the persistent log."""
    init_db()
    with _connect() as conn:
        conn.execute(
            "INSERT INTO conversation_logs (role, content) VALUES (?, ?)",
            (role, content),
        )
        conn.commit()


def load_recent_history(limit=40):
    """
    Load the last `limit` messages from the log as a list of
    {'role': ..., 'content': ...} dicts ready for ollama.chat().
    """
    init_db()
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT role, content
            FROM conversation_logs
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        )
        rows = cur.fetchall()
    return [{"role": row[0], "content": row[1]} for row in reversed(rows)]


def load_all_logs():
    """Return every log entry as (timestamp, role, content) tuples."""
    init_db()
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT timestamp, role, content FROM conversation_logs ORDER BY id ASC"
        )
        return cur.fetchall()


def clear_conversation_logs():
    """Wipe the conversation history (keeps long-term memories intact)."""
    init_db()
    with _connect() as conn:
        conn.execute("DELETE FROM conversation_logs")
        conn.commit()


def log_telemetry(event_name, source=None, value=None, session_id=None):
    """Append one telemetry event row."""
    init_db()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO telemetry_events (event_name, source, value, session_id)
            VALUES (?, ?, ?, ?)
            """,
            (event_name, source, value, session_id),
        )
        conn.commit()


def load_telemetry_summary():
    """Return lightweight aggregate telemetry for UI display."""
    init_db()
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM telemetry_events")
        total_events = cur.fetchone()[0] or 0

        cur.execute(
            "SELECT COUNT(*) FROM telemetry_events WHERE event_name = 'command_received'"
        )
        total_commands = cur.fetchone()[0] or 0

        cur.execute(
            "SELECT COUNT(*) FROM telemetry_events WHERE event_name = 'error'"
        )
        total_errors = cur.fetchone()[0] or 0

        cur.execute("SELECT MAX(timestamp) FROM telemetry_events")
        last_event = cur.fetchone()[0]

    return {
        "total_events": total_events,
        "total_commands": total_commands,
        "total_errors": total_errors,
        "last_event": last_event,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }


def _encode_setting(value):
    return json.dumps(value)


def _decode_setting(value):
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def save_setting(key, value):
    init_db()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO settings (key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = CURRENT_TIMESTAMP
            """,
            (key, _encode_setting(value)),
        )
        conn.commit()


def load_setting(key, default=None):
    init_db()
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cur.fetchone()
    if not row:
        return default
    return _decode_setting(row[0])


def load_all_settings():
    init_db()
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT key, value FROM settings ORDER BY key ASC")
        rows = cur.fetchall()
    return {key: _decode_setting(value) for key, value in rows}


def save_scheduled_item(item_id, kind, task, due_at, created_at):
    init_db()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO scheduled_items (id, kind, task, due_at, created_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                kind = excluded.kind,
                task = excluded.task,
                due_at = excluded.due_at,
                created_at = excluded.created_at
            """,
            (item_id, kind, task, due_at, created_at),
        )
        conn.commit()


def delete_scheduled_item(item_id):
    init_db()
    with _connect() as conn:
        conn.execute("DELETE FROM scheduled_items WHERE id = ?", (item_id,))
        conn.commit()


def delete_scheduled_items(item_ids):
    init_db()
    ids = list(item_ids)
    if not ids:
        return
    with _connect() as conn:
        conn.executemany(
            "DELETE FROM scheduled_items WHERE id = ?",
            [(item_id,) for item_id in ids],
        )
        conn.commit()


def clear_scheduled_items():
    init_db()
    with _connect() as conn:
        conn.execute("DELETE FROM scheduled_items")
        conn.commit()


def load_scheduled_items():
    init_db()
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, kind, task, due_at, created_at
            FROM scheduled_items
            ORDER BY due_at ASC, id ASC
            """
        )
        rows = cur.fetchall()
    return [
        {
            "id": row[0],
            "kind": row[1],
            "task": row[2],
            "due_at": row[3],
            "created_at": row[4],
        }
        for row in rows
    ]


def upsert_task_memory(title, notes="", status="active"):
    init_db()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO task_memory (title, notes, status, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(title) DO UPDATE SET
                notes = excluded.notes,
                status = excluded.status,
                updated_at = CURRENT_TIMESTAMP
            """,
            (title, notes, status),
        )
        conn.commit()


def save_task_memory(title, notes="", status="active"):
    init_db()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO task_memory (title, notes, status, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (title, notes, status),
        )
        conn.commit()


def load_task_memory(status=None, limit=20):
    init_db()
    query = """
        SELECT id, title, notes, status, updated_at
        FROM task_memory
    """
    params = []
    if status:
        query += " WHERE status = ?"
        params.append(status)
    query += " ORDER BY updated_at DESC LIMIT ?"
    params.append(limit)
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute(query, tuple(params))
        rows = cur.fetchall()
    return [
        {
            "id": row[0],
            "title": row[1],
            "notes": row[2] or "",
            "status": row[3],
            "updated_at": row[4],
        }
        for row in rows
    ]


def update_task_status(title, status):
    init_db()
    with _connect() as conn:
        conn.execute(
            """
            UPDATE task_memory
            SET status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE lower(title) = lower(?)
            """,
            (status, title),
        )
        conn.commit()


def save_automation(name, automation_type, payload):
    init_db()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO automations (name, automation_type, payload, created_at, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT(name) DO UPDATE SET
                automation_type = excluded.automation_type,
                payload = excluded.payload,
                updated_at = CURRENT_TIMESTAMP
            """,
            (name, automation_type, _encode_setting(payload)),
        )
        conn.commit()


def load_automation(name):
    init_db()
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT name, automation_type, payload, created_at, updated_at, last_run_at
            FROM automations
            WHERE lower(name) = lower(?)
            """,
            (name,),
        )
        row = cur.fetchone()
    if not row:
        return None
    return {
        "name": row[0],
        "automation_type": row[1],
        "payload": _decode_setting(row[2]),
        "created_at": row[3],
        "updated_at": row[4],
        "last_run_at": row[5],
    }


def load_automations(limit=20):
    init_db()
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT name, automation_type, payload, created_at, updated_at, last_run_at
            FROM automations
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            (limit,),
        )
        rows = cur.fetchall()
    return [
        {
            "name": row[0],
            "automation_type": row[1],
            "payload": _decode_setting(row[2]),
            "created_at": row[3],
            "updated_at": row[4],
            "last_run_at": row[5],
        }
        for row in rows
    ]


def mark_automation_ran(name):
    init_db()
    with _connect() as conn:
        conn.execute(
            """
            UPDATE automations
            SET last_run_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE lower(name) = lower(?)
            """,
            (name,),
        )
        conn.commit()
