import os
import sqlite3

def get_connection():
    url = os.getenv("TURSO_DATABASE_URL")
    token = os.getenv("TURSO_AUTH_TOKEN")
    if url and token:
        return sqlite3.connect(f"{url}?auth_token={token}")
    return sqlite3.connect("bot.db")

conn = get_connection()
cur = conn.cursor()
conn.row_factory = sqlite3.Row

# === 建表 ===
cur.execute('''
CREATE TABLE IF NOT EXISTS folders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
''')

cur.execute('''
CREATE TABLE IF NOT EXISTS media (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    folder_id INTEGER NOT NULL REFERENCES folders(id) ON DELETE CASCADE,
    file_id TEXT NOT NULL,
    media_type TEXT NOT NULL,
    caption TEXT,
    added_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
''')
conn.commit()

# === 你的 bot.py 调用的全部函数 ===
class Database:
    def __init__(self):
        self.conn = conn
        self.cur = cur

    def create_folder(self, name):
        try:
            self.cur.execute("INSERT INTO folders (name) VALUES (?)", (name,))
            self.conn.commit()
            return self.cur.lastrowid
        except:
            return None

    def folder_exists(self, name):
        self.cur.execute("SELECT 1 FROM folders WHERE name = ?", (name,))
        return self.cur.fetchone() is not None

    def get_all_folders(self):
        self.cur.execute("SELECT * FROM folders ORDER BY name")
        return [dict(row) for row in self.cur.fetchall()]

    def get_folder(self, folder_id):
        self.cur.execute("SELECT * FROM folders WHERE id = ?", (folder_id,))
        row = self.cur.fetchone()
        return dict(row) if row else None

    def count_media(self, folder_id):
        self.cur.execute("SELECT COUNT(*) FROM media WHERE folder_id = ?", (folder_id,))
        return self.cur.fetchone()[0]

    def get_media(self, folder_id):
        self.cur.execute("SELECT * FROM media WHERE folder_id = ? ORDER BY added_at DESC", (folder_id,))
        return [dict(row) for row in self.cur.fetchall()]

    def add_media(self, folder_id, file_id, media_type, caption=""):
        self.cur.execute('''
            INSERT INTO media (folder_id, file_id, media_type, caption)
            VALUES (?, ?, ?, ?)
        ''', (folder_id, file_id, media_type, caption))
        self.conn.commit()

    def delete_folder(self, folder_id):
        self.cur.execute("DELETE FROM folders WHERE id = ?", (folder_id,))
        self.conn.commit()

    def rename_folder(self, folder_id, new_name):
        self.cur.execute("UPDATE folders SET name = ? WHERE id = ?", (new_name, folder_id))
        self.conn.commit()

    def get_media_by_id(self, media_id):
        self.cur.execute("SELECT * FROM media WHERE id = ?", (media_id,))
        row = self.cur.fetchone()
        return dict(row) if row else None

    def delete_media(self, media_id):
        self.cur.execute("DELETE FROM media WHERE id = ?", (media_id,))
        self.conn.commit()
