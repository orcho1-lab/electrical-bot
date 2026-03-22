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
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            _exec(conn, f"""
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    title TEXT,
                    user_id TEXT,
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

            # Add columns missing from older DB versions
            if _USE_PG:
                try: _exec(conn, "ALTER TABLE conversations ADD COLUMN user_id TEXT")
                except Exception: pass
            else:
                try: conn.execute("ALTER TABLE conversations ADD COLUMN user_id TEXT")
                except Exception: pass

                for col, typedef in [
                    ("solution", "TEXT DEFAULT ''"),
                    ("image_url", "TEXT DEFAULT ''"),
                    ("difficulty", "INTEGER DEFAULT 0"),
                    ("sort_order", "INTEGER DEFAULT 0"),
                    ("embedding", "TEXT DEFAULT ''"),
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

    # ── Users ────────────────────────────────────────────────────────────────

    def get_user_by_email(self, email: str) -> dict:
        with self._conn() as conn:
            cur = _exec(conn, "SELECT * FROM users WHERE email=?", (email,))
            rows = _rows(cur)
            return rows[0] if rows else None

    def create_user(self, email: str, password_hash: str) -> str:
        user_id = str(uuid.uuid4())
        with self._conn() as conn:
            _exec(conn, "INSERT INTO users (id, email, password_hash) VALUES (?, ?, ?)", (user_id, email, password_hash))
        return user_id

    def update_user_password(self, user_id: str, password_hash: str):
        with self._conn() as conn:
            _exec(conn, "UPDATE users SET password_hash=? WHERE id=?", (password_hash, user_id))

    # ── Conversations ────────────────────────────────────────────────────────

    def create_conversation(self, title: str = "שיחה חדשה", user_id: str = None) -> str:
        conv_id = str(uuid.uuid4())
        with self._conn() as conn:
            _exec(conn, "INSERT INTO conversations (id, title, user_id) VALUES (?, ?, ?)", (conv_id, title, user_id))
        return conv_id

    def update_conversation_title(self, conv_id: str, title: str, user_id: str = None):
        with self._conn() as conn:
            _exec(conn,
                  "UPDATE conversations SET title=?, updated_at=CURRENT_TIMESTAMP WHERE id=? AND (user_id=? OR user_id IS NULL)",
                  (title, conv_id, user_id))

    def get_conversations(self, search: str = "", user_id: str = None) -> list[dict]:
        with self._conn() as conn:
            if search:
                cur = _exec(conn,
                            "SELECT * FROM conversations WHERE title LIKE ? AND (user_id=? OR user_id IS NULL) ORDER BY updated_at DESC",
                            (f"%{search}%", user_id))
            else:
                cur = _exec(conn, "SELECT * FROM conversations WHERE (user_id=? OR user_id IS NULL) ORDER BY updated_at DESC", (user_id,))
            return _rows(cur)

    def delete_conversation(self, conv_id: str, user_id: str = None):
        with self._conn() as conn:
            _exec(conn, "DELETE FROM messages WHERE conversation_id IN (SELECT id FROM conversations WHERE id=? AND (user_id=? OR user_id IS NULL))", (conv_id, user_id))
            _exec(conn, "DELETE FROM conversations WHERE id=? AND (user_id=? OR user_id IS NULL)", (conv_id, user_id))

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

    def get_learnings(self) -> list[dict]:
        with self._conn() as conn:
            cur = _exec(conn,
                        "SELECT id, summary FROM learnings ORDER BY created_at DESC LIMIT 20")
            return _rows(cur)
            
    def delete_learning(self, learning_id: int):
        with self._conn() as conn:
            _exec(conn, "DELETE FROM learnings WHERE id=?", (learning_id,))

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
                      solution: str = "", image_url: str = "", embedding: str = "") -> int:
        with self._conn() as conn:
            return _insert_returning_id(
                conn,
                "INSERT INTO questions (text, topic, source, solution, image_url, embedding) VALUES (?, ?, ?, ?, ?, ?)",
                (text, topic, source, solution, image_url, embedding),
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
                        "SELECT id, text, topic, solution, embedding FROM questions "
                        "WHERE solution IS NOT NULL AND solution != '' ORDER BY id")
            return _rows(cur)

    def delete_question(self, question_id: int):
        with self._conn() as conn:
            _exec(conn, "DELETE FROM questions WHERE id=?", (question_id,))

    def deduplicate_questions(self) -> int:
        with self._conn() as conn:
            cur = _exec(conn, "SELECT id, text, embedding FROM questions ORDER BY id ASC")
            rows = _rows(cur)

        seen = []
        to_delete = []
        
        import json, math
        def cosine_sim(v1, v2):
            if not v1 or not v2: return 0.0
            norm1 = sum(a*a for a in v1)
            norm2 = sum(b*b for b in v2)
            if norm1 == 0 or norm2 == 0: return 0.0
            return sum(a*b for a, b in zip(v1, v2)) / math.sqrt(norm1 * norm2)

        for row in rows:
            norm = _normalize_text(row["text"])
            if not norm:
                continue
                
            emb = None
            if row.get("embedding"):
                try: emb = json.loads(row["embedding"])
                except: pass

            is_dup = False
            for seen_id, seen_norm, seen_emb in seen:
                if emb and seen_emb:
                    if cosine_sim(emb, seen_emb) > 0.96:
                        is_dup = True
                        break
                else:
                    if len(norm) > 20 and len(seen_norm) > 20:
                        shorter, longer = (norm, seen_norm) if len(norm) <= len(seen_norm) else (seen_norm, norm)
                        if shorter in longer:
                            is_dup = True
                            break
            if is_dup:
                to_delete.append(row["id"])
            else:
                seen.append((row["id"], norm, emb))

        if to_delete:
            ph = "%s" if _USE_PG else "?"
            placeholders = ",".join([ph] * len(to_delete))
            with self._conn() as conn:
                _exec(conn, f"DELETE FROM questions WHERE id IN ({placeholders})", to_delete)

        return len(to_delete)
