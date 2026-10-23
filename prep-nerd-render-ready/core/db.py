import json
import sqlite3
from pathlib import Path
from typing import Any


class Database:
    """SQLite persistence with explicit per-user ownership on every record."""

    TABLES = {"sources", "artifacts", "mistakes"}

    def __init__(self, path):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.init()

    def conn(self):
        connection = sqlite3.connect(self.path, timeout=15)
        connection.row_factory = sqlite3.Row
        return connection

    def init(self):
        with self.conn() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS sources (
                    id INTEGER PRIMARY KEY, title TEXT, kind TEXT, content TEXT,
                    source_ref TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    user_id TEXT NOT NULL DEFAULT 'local'
                );
                CREATE TABLE IF NOT EXISTS artifacts (
                    id INTEGER PRIMARY KEY, kind TEXT, title TEXT, payload TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    user_id TEXT NOT NULL DEFAULT 'local'
                );
                CREATE TABLE IF NOT EXISTS mistakes (
                    id INTEGER PRIMARY KEY, payload TEXT,
                    status TEXT DEFAULT 'Needs More Practice',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    user_id TEXT NOT NULL DEFAULT 'local'
                );
                
                CREATE TABLE IF NOT EXISTS google_users (
                    google_sub TEXT PRIMARY KEY,
                    email TEXT NOT NULL,
                    name TEXT NOT NULL DEFAULT '',
                    picture TEXT NOT NULL DEFAULT '',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                """
            )
            # Existing installations are upgraded in place. Legacy rows retain the
            # "local" owner and cannot be seen by authenticated users by default.
            for table in self.TABLES:
                columns = {row["name"] for row in connection.execute(f"PRAGMA table_info({table})")}
                if "user_id" not in columns:
                    connection.execute(
                        f"ALTER TABLE {table} ADD COLUMN user_id TEXT NOT NULL DEFAULT 'local'"
                    )
            connection.executescript(
                """
                CREATE INDEX IF NOT EXISTS idx_sources_user_created ON sources(user_id, id DESC);
                CREATE INDEX IF NOT EXISTS idx_artifacts_user_kind ON artifacts(user_id, kind, id DESC);
                CREATE INDEX IF NOT EXISTS idx_mistakes_user_created ON mistakes(user_id, id DESC);
                """
            )

    @staticmethod
    def _payload(value: Any):
        return json.dumps(value, ensure_ascii=False)

    @staticmethod
    def _decode_artifact(row):
        item = dict(row)
        try:
            item["payload"] = json.loads(item.get("payload") or "null")
        except (TypeError, json.JSONDecodeError):
            item["payload"] = item.get("payload")
        return item

    def add_source(self, title, kind, content, ref="", user_id="local"):
        with self.conn() as connection:
            return connection.execute(
                "INSERT INTO sources(title,kind,content,source_ref,user_id) VALUES(?,?,?,?,?)",
                (title, kind, content, ref, user_id),
            ).lastrowid

    def sources(self, user_id="local"):
        with self.conn() as connection:
            rows = connection.execute(
                "SELECT * FROM sources WHERE user_id=? ORDER BY id DESC", (user_id,)
            ).fetchall()
            return [dict(row) for row in rows]

    def save(self, kind, title, payload, user_id="local"):
        with self.conn() as connection:
            return connection.execute(
                "INSERT INTO artifacts(kind,title,payload,user_id) VALUES(?,?,?,?)",
                (kind, title, self._payload(payload), user_id),
            ).lastrowid

    def artifacts(self, kind=None, user_id="local"):
        query = "SELECT * FROM artifacts WHERE user_id=?"
        args = [user_id]
        if kind:
            query += " AND kind=?"
            args.append(kind)
        query += " ORDER BY id DESC"
        with self.conn() as connection:
            return [self._decode_artifact(row) for row in connection.execute(query, args).fetchall()]

    def get_artifact(self, artifact_id, user_id="local"):
        with self.conn() as connection:
            row = connection.execute(
                "SELECT * FROM artifacts WHERE id=? AND user_id=?", (artifact_id, user_id)
            ).fetchone()
            return self._decode_artifact(row) if row else None

    def update_artifact(self, artifact_id, payload, title=None, user_id="local"):
        with self.conn() as connection:
            if title is None:
                cursor = connection.execute(
                    "UPDATE artifacts SET payload=? WHERE id=? AND user_id=?",
                    (self._payload(payload), artifact_id, user_id),
                )
            else:
                cursor = connection.execute(
                    "UPDATE artifacts SET title=?,payload=? WHERE id=? AND user_id=?",
                    (title, self._payload(payload), artifact_id, user_id),
                )
            return cursor.rowcount == 1

    def add_mistake(self, payload, user_id="local"):
        with self.conn() as connection:
            return connection.execute(
                "INSERT INTO mistakes(payload,status,user_id) VALUES(?,?,?)",
                (self._payload(payload), payload.get("status", "Needs More Practice"), user_id),
            ).lastrowid

    def mistakes(self, user_id="local"):
        with self.conn() as connection:
            rows = connection.execute(
                "SELECT * FROM mistakes WHERE user_id=? ORDER BY id DESC", (user_id,)
            ).fetchall()
            result = []
            for row in rows:
                item = dict(row)
                try:
                    item["payload"] = json.loads(item["payload"])
                except (TypeError, json.JSONDecodeError):
                    item["payload"] = {}
                if isinstance(item["payload"], dict):
                    item["payload"]["status"] = item["status"]
                result.append(item)
            return result

    def update_mistake(self, mistake_id, status, user_id="local"):
        with self.conn() as connection:
            cursor = connection.execute(
                "UPDATE mistakes SET status=? WHERE id=? AND user_id=?",
                (status, mistake_id, user_id),
            )
            return cursor.rowcount == 1

    def delete(self, table, item_id, user_id="local"):
        if table not in self.TABLES:
            raise ValueError("invalid table")
        with self.conn() as connection:
            cursor = connection.execute(
                f"DELETE FROM {table} WHERE id=? AND user_id=?", (item_id, user_id)
            )
            return cursor.rowcount == 1
    
    def register_google_user(self, google_sub, email, name="", picture=""):
        with self.conn() as connection:
            connection.execute(
                """
                INSERT INTO google_users (google_sub, email, name, picture)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(google_sub) DO UPDATE SET
                    email=excluded.email,
                    name=excluded.name,
                    picture=excluded.picture,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (google_sub, email, name, picture),
            )
        return f"google:{google_sub}"

    def transfer_workspace(self, old_owner, new_owner):
        if not old_owner or old_owner == new_owner:
            return
        with self.conn() as connection:
            for table in self.TABLES:
                connection.execute(
                    f"UPDATE {table} SET user_id=? WHERE user_id=?",
                    (new_owner, old_owner),
                )

