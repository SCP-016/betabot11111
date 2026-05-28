import os
import libsql_experimental as libsql


class Database:
    def __init__(self):
        url = os.environ["TURSO_DATABASE_URL"]
        auth_token = os.environ.get("TURSO_AUTH_TOKEN", "")
        self.conn = libsql.connect(database=url, auth_token=auth_token)
        self._init_tables()

    def _init_tables(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY
            );

            CREATE TABLE IF NOT EXISTS folders (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name    TEXT    NOT NULL,
                UNIQUE(user_id, name),
                FOREIGN KEY(user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS medias (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                folder_id  INTEGER NOT NULL,
                file_id    TEXT    NOT NULL,
                media_type TEXT    NOT NULL,
                caption    TEXT    DEFAULT '',
                created_at TEXT    DEFAULT (datetime('now')),
                FOREIGN KEY(folder_id) REFERENCES folders(id) ON DELETE CASCADE
            );
        """)
        self.conn.commit()

    # ── Users ──────────────────────────────────────────────────────────────

    def ensure_user(self, user_id: int):
        self.conn.execute(
            "INSERT OR IGNORE INTO users (id) VALUES (?)", (user_id,)
        )
        self.conn.commit()

    # ── Folders ────────────────────────────────────────────────────────────

    def get_folders(self, user_id: int) -> list[dict]:
        rows = self.conn.execute(
            """
            SELECT f.id, f.name, COUNT(m.id) AS count
            FROM folders f
            LEFT JOIN medias m ON m.folder_id = f.id
            WHERE f.user_id = ?
            GROUP BY f.id
            ORDER BY f.name
            """,
            (user_id,),
        ).fetchall()
        return [{"id": r[0], "name": r[1], "count": r[2]} for r in rows]

    def get_folder(self, user_id: int, folder_id: int) -> dict | None:
        row = self.conn.execute(
            "SELECT id, name FROM folders WHERE id = ? AND user_id = ?",
            (folder_id, user_id),
        ).fetchone()
        return {"id": row[0], "name": row[1]} if row else None

    def folder_name_exists(self, user_id: int, name: str) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM folders WHERE user_id = ? AND name = ?",
            (user_id, name),
        ).fetchone()
        return row is not None

    def create_folder(self, user_id: int, name: str):
        self.conn.execute(
            "INSERT INTO folders (user_id, name) VALUES (?, ?)", (user_id, name)
        )
        self.conn.commit()

    def rename_folder(self, user_id: int, folder_id: int, new_name: str):
        self.conn.execute(
            "UPDATE folders SET name = ? WHERE id = ? AND user_id = ?",
            (new_name, folder_id, user_id),
        )
        self.conn.commit()

    def delete_folder(self, user_id: int, folder_id: int):
        self.conn.execute(
            "DELETE FROM folders WHERE id = ? AND user_id = ?", (folder_id, user_id)
        )
        self.conn.commit()

    # ── Medias ─────────────────────────────────────────────────────────────

    def get_medias(self, folder_id: int) -> list[dict]:
        rows = self.conn.execute(
            """
            SELECT id, file_id, media_type, caption, created_at
            FROM medias
            WHERE folder_id = ?
            ORDER BY created_at DESC
            """,
            (folder_id,),
        ).fetchall()
        return [
            {"id": r[0], "file_id": r[1], "media_type": r[2], "caption": r[3], "created_at": r[4]}
            for r in rows
        ]

    def get_media(self, media_id: int) -> dict | None:
        row = self.conn.execute(
            "SELECT id, file_id, media_type, caption FROM medias WHERE id = ?",
            (media_id,),
        ).fetchone()
        return {"id": row[0], "file_id": row[1], "media_type": row[2], "caption": row[3]} if row else None

    def add_media(self, folder_id: int, file_id: str, media_type: str, caption: str):
        self.conn.execute(
            "INSERT INTO medias (folder_id, file_id, media_type, caption) VALUES (?, ?, ?, ?)",
            (folder_id, file_id, media_type, caption),
        )
        self.conn.commit()

    def delete_media(self, media_id: int):
        self.conn.execute("DELETE FROM medias WHERE id = ?", (media_id,))
        self.conn.commit()

    def count_medias(self, folder_id: int) -> int:
        row = self.conn.execute(
            "SELECT COUNT(*) FROM medias WHERE folder_id = ?", (folder_id,)
        ).fetchone()
        return row[0] if row else 0
