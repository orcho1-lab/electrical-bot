import re
import sqlite3
import uuid
from datetime import datetime


def _normalize_text(text: str) -> str:
    """Normalize question text for duplicate comparison."""
    t = text.strip()
    t = re.sub(r'\s+', ' ', t)           # collapse whitespace
    t = re.sub(r'[.,;:!?()\'\"]+', '', t) # remove punctuation
    return t.lower()


class Database:
    def __init__(self, db_path="conversations.db"):
        self.db_path = db_path
        self.init_db()

    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        with self.get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    title TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    conversation_id TEXT,
                    role TEXT,
                    content TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS learnings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    summary TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS questions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    text TEXT NOT NULL,
                    topic TEXT DEFAULT '',
                    source TEXT DEFAULT '',
                    solution TEXT DEFAULT '',
                    image_url TEXT DEFAULT '',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # Migrations: add columns that may be missing from older table versions
            for col, typedef in [
                ("solution", "TEXT DEFAULT ''"),
                ("image_url", "TEXT DEFAULT ''"),
                ("difficulty", "INTEGER DEFAULT 0"),
                ("sort_order", "INTEGER DEFAULT 0"),
            ]:
                try:
                    conn.execute(f"ALTER TABLE questions ADD COLUMN {col} {typedef}")
                except Exception:
                    pass  # column already exists

            # Indexes for performance
            conn.execute("CREATE INDEX IF NOT EXISTS idx_questions_topic ON questions(topic)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_questions_source ON questions(source)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_conv_updated ON conversations(updated_at)")

    def create_conversation(self, title="שיחה חדשה"):
        conv_id = str(uuid.uuid4())
        with self.get_connection() as conn:
            conn.execute(
                "INSERT INTO conversations (id, title) VALUES (?, ?)",
                (conv_id, title)
            )
        return conv_id

    def update_conversation_title(self, conv_id, title):
        with self.get_connection() as conn:
            conn.execute(
                "UPDATE conversations SET title=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (title, conv_id)
            )

    def get_conversations(self, search: str = ""):
        with self.get_connection() as conn:
            if search:
                rows = conn.execute(
                    "SELECT * FROM conversations WHERE title LIKE ? ORDER BY updated_at DESC",
                    (f"%{search}%",)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM conversations ORDER BY updated_at DESC"
                ).fetchall()
        return [dict(row) for row in rows]

    def save_message(self, conversation_id, role, content):
        msg_id = str(uuid.uuid4())
        with self.get_connection() as conn:
            conn.execute(
                "INSERT INTO messages (id, conversation_id, role, content) VALUES (?, ?, ?, ?)",
                (msg_id, conversation_id, role, content)
            )
            conn.execute(
                "UPDATE conversations SET updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (conversation_id,)
            )

    def get_messages(self, conversation_id):
        with self.get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM messages WHERE conversation_id=? ORDER BY created_at ASC",
                (conversation_id,)
            ).fetchall()
        return [dict(row) for row in rows]

    def delete_conversation(self, conversation_id):
        with self.get_connection() as conn:
            conn.execute("DELETE FROM messages WHERE conversation_id=?", (conversation_id,))
            conn.execute("DELETE FROM conversations WHERE id=?", (conversation_id,))

    def save_learning(self, summary: str):
        with self.get_connection() as conn:
            conn.execute("INSERT INTO learnings (summary) VALUES (?)", (summary,))

    def get_learnings(self) -> list:
        with self.get_connection() as conn:
            rows = conn.execute(
                "SELECT summary FROM learnings ORDER BY created_at DESC LIMIT 20"
            ).fetchall()
        return [row["summary"] for row in rows]

    def question_exists(self, text: str) -> bool:
        """Check if a question with similar text already exists (normalized comparison)."""
        normalized = _normalize_text(text)
        if not normalized:
            return False
        with self.get_connection() as conn:
            rows = conn.execute("SELECT text FROM questions").fetchall()
            for row in rows:
                if _normalize_text(row["text"]) == normalized:
                    return True
                # Also check if one is a substring of the other (>80% overlap)
                existing = _normalize_text(row["text"])
                if len(normalized) > 20 and len(existing) > 20:
                    shorter, longer = (normalized, existing) if len(normalized) <= len(existing) else (existing, normalized)
                    if shorter in longer:
                        return True
            return False

    def save_question(self, text: str, topic: str = "", source: str = "", solution: str = "", image_url: str = "") -> int:
        with self.get_connection() as conn:
            cursor = conn.execute(
                "INSERT INTO questions (text, topic, source, solution, image_url) VALUES (?, ?, ?, ?, ?)",
                (text, topic, source, solution, image_url)
            )
            return cursor.lastrowid

    def get_questions(self) -> list:
        with self.get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM questions ORDER BY created_at DESC"
            ).fetchall()
        return [dict(row) for row in rows]

    def update_question(self, question_id: int, **fields):
        """Update specific fields of a question."""
        if not fields:
            return
        set_clause = ", ".join(f"{k}=?" for k in fields)
        values = list(fields.values()) + [question_id]
        with self.get_connection() as conn:
            conn.execute(f"UPDATE questions SET {set_clause} WHERE id=?", values)

    def get_unsolved_questions(self) -> list:
        """Get all questions that don't have a solution yet."""
        with self.get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM questions WHERE solution IS NULL OR solution = '' ORDER BY id"
            ).fetchall()
        return [dict(row) for row in rows]

    def deduplicate_questions(self) -> int:
        """Remove duplicate questions, keeping the oldest (lowest id) of each group.
        Returns the number of duplicates removed.
        """
        with self.get_connection() as conn:
            rows = conn.execute("SELECT id, text FROM questions ORDER BY id ASC").fetchall()

        seen = {}  # normalized_text -> first id
        to_delete = []

        for row in rows:
            norm = _normalize_text(row["text"])
            if not norm:
                continue
            # Check exact match
            if norm in seen:
                to_delete.append(row["id"])
                continue
            # Check substring overlap
            is_dup = False
            for existing_norm, existing_id in seen.items():
                if len(norm) > 20 and len(existing_norm) > 20:
                    shorter, longer = (norm, existing_norm) if len(norm) <= len(existing_norm) else (existing_norm, norm)
                    if shorter in longer:
                        to_delete.append(row["id"])
                        is_dup = True
                        break
            if not is_dup:
                seen[norm] = row["id"]

        if to_delete:
            with self.get_connection() as conn:
                placeholders = ",".join("?" * len(to_delete))
                conn.execute(f"DELETE FROM questions WHERE id IN ({placeholders})", to_delete)

        return len(to_delete)

    def get_solved_questions(self) -> list:
        """Get all questions that have a non-empty solution."""
        with self.get_connection() as conn:
            rows = conn.execute(
                "SELECT id, text, topic, solution FROM questions "
                "WHERE solution IS NOT NULL AND solution != '' ORDER BY id"
            ).fetchall()
        return [dict(row) for row in rows]

    def delete_question(self, question_id: int):
        with self.get_connection() as conn:
            conn.execute("DELETE FROM questions WHERE id=?", (question_id,))
