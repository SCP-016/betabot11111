import os
from libsql_client import create_client

# 从环境变量读取 Turso 连接信息
TURSO_URL = os.getenv("TURSO_DATABASE_URL")
TURSO_TOKEN = os.getenv("TURSO_AUTH_TOKEN")

if not TURSO_URL or not TURSO_TOKEN:
    raise Exception("请设置 TURSO_DATABASE_URL 和 TURSO_AUTH_TOKEN")

# 创建连接
async def get_db():
    client = create_client(TURSO_URL, auth_token=TURSO_TOKEN)
    return client

# ---------------------- 表结构 ----------------------
async def init_db():
    db = await get_db()
    
    await db.execute('''
    CREATE TABLE IF NOT EXISTS folders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        chat_id INTEGER NOT NULL,
        UNIQUE(name, chat_id)
    )
    ''')

    await db.execute('''
    CREATE TABLE IF NOT EXISTS files (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        folder_id INTEGER NOT NULL,
        file_id TEXT NOT NULL,
        file_type TEXT,
        caption TEXT,
        FOREIGN KEY (folder_id) REFERENCES folders (id)
    )
    ''')
    
    await db.close()

# ---------------------- 工具函数 ----------------------
async def create_folder(name, chat_id):
    db = await get_db()
    try:
        result = await db.execute(
            "INSERT INTO folders (name, chat_id) VALUES (?, ?)",
            [name, chat_id]
        )
        return result.last_insert_rowid
    except Exception as e:
        print("创建文件夹失败：", e)
        return None
    finally:
        await db.close()

async def get_user_folders(chat_id):
    db = await get_db()
    rows = await db.execute(
        "SELECT * FROM folders WHERE chat_id = ?",
        [chat_id]
    )
    await db.close()
    return rows

async def save_file(folder_id, file_id, file_type="photo", caption=""):
    db = await get_db()
    await db.execute(
        "INSERT INTO files (folder_id, file_id, file_type, caption) VALUES (?, ?, ?, ?)",
        [folder_id, file_id, file_type, caption]
    )
    await db.close()

async def get_files_in_folder(folder_id):
    db = await get_db()
    rows = await db.execute(
        "SELECT * FROM files WHERE folder_id = ?",
        [folder_id]
    )
    await db.close()
    return rows

async def get_folder_id_by_name(name, chat_id):
    db = await get_db()
    rows = await db.execute(
        "SELECT id FROM folders WHERE name = ? AND chat_id = ?",
        [name, chat_id]
    )
    await db.close()
    return rows[0]["id"] if rows else None
