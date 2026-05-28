import os
import sqlite3

# 自动兼容本地 + Turso（不用改 bot.py！）
def get_connection():
    url = os.getenv("TURSO_DATABASE_URL")
    token = os.getenv("TURSO_AUTH_TOKEN")
    
    if url and token and "libsql://" in url:
        # 云数据库 Turso
        return sqlite3.connect(f"{url}?auth_token={token}")
    else:
        # 本地 fallback
        return sqlite3.connect("bot.db")

# 全局连接（兼容旧代码）
conn = get_connection()
cur = conn.cursor()

# ===================== 表结构（自动创建）=====================
cur.execute('''
CREATE TABLE IF NOT EXISTS folders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    chat_id INTEGER NOT NULL,
    UNIQUE(name, chat_id)
)
''')

cur.execute('''
CREATE TABLE IF NOT EXISTS files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    folder_id INTEGER NOT NULL,
    file_id TEXT NOT NULL,
    file_type TEXT,
    caption TEXT,
    FOREIGN KEY (folder_id) REFERENCES folders (id)
)
''')
conn.commit()

# ===================== 函数完全和原来一样 =====================
def create_folder(name, chat_id):
    try:
        cur.execute("INSERT INTO folders (name, chat_id) VALUES (?, ?)", (name, chat_id))
        conn.commit()
        return cur.lastrowid
    except:
        return None

def get_user_folders(chat_id):
    cur.execute("SELECT * FROM folders WHERE chat_id = ?", (chat_id,))
    return cur.fetchall()

def save_file(folder_id, file_id, file_type="photo", caption=""):
    cur.execute('''
        INSERT INTO files (folder_id, file_id, file_type, caption)
        VALUES (?, ?, ?, ?)
    ''', (folder_id, file_id, file_type, caption))
    conn.commit()

def get_files_in_folder(folder_id):
    cur.execute("SELECT * FROM files WHERE folder_id = ?", (folder_id,))
    return cur.fetchall()

def get_folder_id_by_name(name, chat_id):
    cur.execute("SELECT id FROM folders WHERE name = ? AND chat_id = ?", (name, chat_id))
    row = cur.fetchone()
    return row[0] if row else None
