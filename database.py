import sqlite3
import uuid
from datetime import datetime


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

    def get_conversations(self):
        with self.get_connection() as conn:
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
