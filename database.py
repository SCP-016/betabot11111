import sqlite3
import os
from typing import Optional

DB_PATH = os.environ.get("DB_PATH", "media_bot.db")


class Database:
    def __init__(self):
        self.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_tables()

    def _init_tables(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS folders (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                name    TEXT    NOT NULL UNIQUE,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS media (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                folder_id   INTEGER NOT NULL REFERENCES folders(id) ON DELETE CASCADE,
                file_id     TEXT    NOT NULL,
                media_type  TEXT    NOT NULL CHECK(media_type IN ('photo','video')),
                caption     TEXT    DEFAULT '',
                added_at    DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        """)
        self.conn.commit()

    # ── Folders ──────────────────────────────

    def create_folder(self, name: str) -> int:
        cur = self.conn.execute("INSERT INTO folders (name) VALUES (?)", (name,))
        self.conn.commit()
        return cur.lastrowid

    def get_all_folders(self) -> list:
        return [dict(r) for r in self.conn.execute(
            "SELECT * FROM folders ORDER BY name"
        ).fetchall()]

    def get_folder(self, folder_id: int) -> Optional[dict]:
        row = self.conn.execute(
            "SELECT * FROM folders WHERE id=?", (folder_id,)
        ).fetchone()
        return dict(row) if row else None

    def folder_exists(self, name: str) -> bool:
        return self.conn.execute(
            "SELECT 1 FROM folders WHERE name=?", (name,)
        ).fetchone() is not None

    def rename_folder(self, folder_id: int, new_name: str):
        self.conn.execute(
            "UPDATE folders SET name=? WHERE id=?", (new_name, folder_id)
        )
        self.conn.commit()

    def delete_folder(self, folder_id: int):
        self.conn.execute("DELETE FROM folders WHERE id=?", (folder_id,))
        self.conn.commit()

    # ── Media ─────────────────────────────────

    def add_media(self, folder_id: int, file_id: str, media_type: str, caption: str = "") -> int:
        cur = self.conn.execute(
            "INSERT INTO media (folder_id, file_id, media_type, caption) VALUES (?,?,?,?)",
            (folder_id, file_id, media_type, caption)
        )
        self.conn.commit()
        return cur.lastrowid

    def get_media(self, folder_id: int) -> list:
        return [dict(r) for r in self.conn.execute(
            "SELECT * FROM media WHERE folder_id=? ORDER BY added_at DESC",
            (folder_id,)
        ).fetchall()]

    def count_media(self, folder_id: int) -> int:
        return self.conn.execute(
            "SELECT COUNT(*) FROM media WHERE folder_id=?", (folder_id,)
        ).fetchone()[0]

    def get_media_by_id(self, media_id: int) -> Optional[dict]:
        row = self.conn.execute(
            "SELECT * FROM media WHERE id=?", (media_id,)
        ).fetchone()
        return dict(row) if row else None

    def delete_media(self, media_id: int):
        self.conn.execute("DELETE FROM media WHERE id=?", (media_id,))
        self.conn.commit()
