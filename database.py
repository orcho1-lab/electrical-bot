"""Database layer — SQLite locally, PostgreSQL on Cloud Run.

Set DATABASE_URL env var to a postgres:// connection string to use PostgreSQL.
Leave unset to use SQLite (default: conversations.db).
"""
import os
import re
import sqlite3
import uuid
from contextlib import contextmanager

DATABASE_URL = os.environ.get("DATABASE_URL")
_USE_PG = bool(DATABASE_URL)

if _USE_PG:
    import psycopg2
    import psycopg2.extras


# ---------------------------------------------------------------------------
# Text normalization (shared)
# ---------------------------------------------------------------------------

def _normalize_text(text: str) -> str:
    """Normalize question text for duplicate comparison."""
    t = text.strip()
    t = re.sub(r'\s+', ' ', t)
    t = re.sub(r'[.,;:!?()\'\"]+', '', t)
    return t.lower()


# ---------------------------------------------------------------------------
# Connection context manager
# ---------------------------------------------------------------------------

@contextmanager
def _open_conn(db_path: str):
    """Open a DB connection, commit on success, rollback + close on error."""
    if _USE_PG:
        conn = psycopg2.connect(
            DATABASE_URL,
            cursor_factory=psycopg2.extras.RealDictCursor,
        )
    else:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# SQL helpers
# ---------------------------------------------------------------------------

def _exec(conn, sql: str, params=()):
    """Execute SQL, converting ? → %s for PostgreSQL. Returns cursor."""
    if _USE_PG:
        sql = sql.replace("?", "%s")
        cur = conn.cursor()
        cur.execute(sql, params)
        return cur
    else:
        return conn.execute(sql, params)


def _rows(cursor_or_list) -> list[dict]:
    """Fetch all rows as plain dicts."""
    if isinstance(cursor_or_list, list):
        return [dict(r) for r in cursor_or_list]
    rows = cursor_or_list.fetchall()
    return [dict(r) for r in rows]


def _insert_returning_id(conn, sql: str, params: tuple) -> int:
    """INSERT … RETURNING id (PG) or lastrowid (SQLite)."""
    if _USE_PG:
        sql_pg = sql.replace("?", "%s") + " RETURNING id"
        cur = conn.cursor()
        cur.execute(sql_pg, params)
        return cur.fetchone()["id"]
    else:
        cur = conn.execute(sql, params)
        return cur.lastrowid


# ---------------------------------------------------------------------------
# Database class
# ---------------------------------------------------------------------------

class Database:
    def __init__(self, db_path: str = "conversations.db"):
        self.db_path = db_path
        self.init_db()

    def _conn(self):
        return _open_conn(self.db_path)

    # ── Schema ──────────────────────────────────────────────────────────────

    def init_db(self):
        pk_auto = "SERIAL PRIMARY KEY" if _USE_PG else "INTEGER PRIMARY KEY AUTOINCREMENT"
        with self._conn() as conn:
            _exec(conn, f"""
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    title TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            _exec(conn, f"""
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    conversation_id TEXT,
                    role TEXT,
                    content TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
                )
            """)
            _exec(conn, f"""
                CREATE TABLE IF NOT EXISTS learnings (
                    id {pk_auto},
                    summary TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            _exec(conn, f"""
                CREATE TABLE IF NOT EXISTS questions (
                    id {pk_auto},
                    text TEXT NOT NULL,
                    topic TEXT DEFAULT '',
                    source TEXT DEFAULT '',
                    solution TEXT DEFAULT '',
                    image_url TEXT DEFAULT '',
                    difficulty INTEGER DEFAULT 0,
                    sort_order INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # SQLite-only: add columns missing from older DB versions
            if not _USE_PG:
                for col, typedef in [
                    ("solution", "TEXT DEFAULT ''"),
                    ("image_url", "TEXT DEFAULT ''"),
                    ("difficulty", "INTEGER DEFAULT 0"),
                    ("sort_order", "INTEGER DEFAULT 0"),
                ]:
                    try:
                        conn.execute(f"ALTER TABLE questions ADD COLUMN {col} {typedef}")
                    except Exception:
                        pass

            for idx in [
                "CREATE INDEX IF NOT EXISTS idx_questions_topic ON questions(topic)",
                "CREATE INDEX IF NOT EXISTS idx_questions_source ON questions(source)",
                "CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id)",
                "CREATE INDEX IF NOT EXISTS idx_conv_updated ON conversations(updated_at)",
            ]:
                try:
                    _exec(conn, idx)
                except Exception:
                    pass

    # ── Conversations ────────────────────────────────────────────────────────

    def create_conversation(self, title: str = "שיחה חדשה") -> str:
        conv_id = str(uuid.uuid4())
        with self._conn() as conn:
            _exec(conn, "INSERT INTO conversations (id, title) VALUES (?, ?)", (conv_id, title))
        return conv_id

    def update_conversation_title(self, conv_id: str, title: str):
        with self._conn() as conn:
            _exec(conn,
                  "UPDATE conversations SET title=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                  (title, conv_id))

    def get_conversations(self, search: str = "") -> list[dict]:
        with self._conn() as conn:
            if search:
                cur = _exec(conn,
                            "SELECT * FROM conversations WHERE title LIKE ? ORDER BY updated_at DESC",
                            (f"%{search}%",))
            else:
                cur = _exec(conn, "SELECT * FROM conversations ORDER BY updated_at DESC")
            return _rows(cur)

    def delete_conversation(self, conv_id: str):
        with self._conn() as conn:
            _exec(conn, "DELETE FROM messages WHERE conversation_id=?", (conv_id,))
            _exec(conn, "DELETE FROM conversations WHERE id=?", (conv_id,))

    # ── Messages ─────────────────────────────────────────────────────────────

    def save_message(self, conversation_id: str, role: str, content: str):
        msg_id = str(uuid.uuid4())
        with self._conn() as conn:
            _exec(conn,
                  "INSERT INTO messages (id, conversation_id, role, content) VALUES (?, ?, ?, ?)",
                  (msg_id, conversation_id, role, content))
            _exec(conn,
                  "UPDATE conversations SET updated_at=CURRENT_TIMESTAMP WHERE id=?",
                  (conversation_id,))

    def get_messages(self, conversation_id: str) -> list[dict]:
        with self._conn() as conn:
            cur = _exec(conn,
                        "SELECT * FROM messages WHERE conversation_id=? ORDER BY created_at ASC",
                        (conversation_id,))
            return _rows(cur)

    # ── Learnings ─────────────────────────────────────────────────────────────

    def save_learning(self, summary: str):
        with self._conn() as conn:
            _exec(conn, "INSERT INTO learnings (summary) VALUES (?)", (summary,))

    def get_learnings(self) -> list[str]:
        with self._conn() as conn:
            cur = _exec(conn,
                        "SELECT summary FROM learnings ORDER BY created_at DESC LIMIT 20")
            return [r["summary"] for r in _rows(cur)]

    # ── Questions ─────────────────────────────────────────────────────────────

    def question_exists(self, text: str) -> bool:
        normalized = _normalize_text(text)
        if not normalized:
            return False
        with self._conn() as conn:
            cur = _exec(conn, "SELECT text FROM questions")
            for row in _rows(cur):
                existing = _normalize_text(row["text"])
                if existing == normalized:
                    return True
                if len(normalized) > 20 and len(existing) > 20:
                    shorter, longer = (
                        (normalized, existing) if len(normalized) <= len(existing)
                        else (existing, normalized)
                    )
                    if shorter in longer:
                        return True
        return False

    def save_question(self, text: str, topic: str = "", source: str = "",
                      solution: str = "", image_url: str = "") -> int:
        with self._conn() as conn:
            return _insert_returning_id(
                conn,
                "INSERT INTO questions (text, topic, source, solution, image_url) VALUES (?, ?, ?, ?, ?)",
                (text, topic, source, solution, image_url),
            )

    def get_questions(self) -> list[dict]:
        with self._conn() as conn:
            cur = _exec(conn, "SELECT * FROM questions ORDER BY created_at DESC")
            return _rows(cur)

    def update_question(self, question_id: int, **fields):
        if not fields:
            return
        ph = "%s" if _USE_PG else "?"
        set_clause = ", ".join(f"{k}={ph}" for k in fields)
        values = list(fields.values()) + [question_id]
        with self._conn() as conn:
            _exec(conn, f"UPDATE questions SET {set_clause} WHERE id={ph}", values)

    def get_unsolved_questions(self) -> list[dict]:
        with self._conn() as conn:
            cur = _exec(conn,
                        "SELECT * FROM questions WHERE solution IS NULL OR solution = '' ORDER BY id")
            return _rows(cur)

    def get_solved_questions(self) -> list[dict]:
        with self._conn() as conn:
            cur = _exec(conn,
                        "SELECT id, text, topic, solution FROM questions "
                        "WHERE solution IS NOT NULL AND solution != '' ORDER BY id")
            return _rows(cur)

    def delete_question(self, question_id: int):
        with self._conn() as conn:
            _exec(conn, "DELETE FROM questions WHERE id=?", (question_id,))

    def deduplicate_questions(self) -> int:
        with self._conn() as conn:
            cur = _exec(conn, "SELECT id, text FROM questions ORDER BY id ASC")
            rows = _rows(cur)

        seen: dict[str, int] = {}
        to_delete: list[int] = []

        for row in rows:
            norm = _normalize_text(row["text"])
            if not norm:
                continue
            if norm in seen:
                to_delete.append(row["id"])
                continue
            is_dup = False
            for existing_norm in seen:
                if len(norm) > 20 and len(existing_norm) > 20:
                    shorter, longer = (
                        (norm, existing_norm) if len(norm) <= len(existing_norm)
                        else (existing_norm, norm)
                    )
                    if shorter in longer:
                        to_delete.append(row["id"])
                        is_dup = True
                        break
            if not is_dup:
                seen[norm] = row["id"]

        if to_delete:
            ph = "%s" if _USE_PG else "?"
            placeholders = ",".join([ph] * len(to_delete))
            with self._conn() as conn:
                _exec(conn, f"DELETE FROM questions WHERE id IN ({placeholders})", to_delete)

        return len(to_delete)
