import os
import libsql

# 从环境变量读取 Turso 连接信息（Render 里已配置好）
TURSO_URL = os.getenv("TURSO_DATABASE_URL")
TURSO_TOKEN = os.getenv("TURSO_AUTH_TOKEN")

if not TURSO_URL or not TURSO_TOKEN:
    raise Exception("❌ 缺少 Turso 环境变量：TURSO_DATABASE_URL 或 TURSO_AUTH_TOKEN")

# 连接 Turso 云端数据库
conn = libsql.connect(
    database=TURSO_URL,
    auth_token=TURSO_TOKEN
)
cur = conn.cursor()

# ---------------------- 表结构（直接覆盖，兼容旧数据）----------------------
# 文件夹表
cur.execute('''
CREATE TABLE IF NOT EXISTS folders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    chat_id INTEGER NOT NULL,
    UNIQUE(name, chat_id)
)
''')

# 文件/图片表
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

# ---------------------- 常用函数（和你旧版用法完全一样）----------------------
# 创建文件夹
def create_folder(name, chat_id):
    try:
        cur.execute("INSERT INTO folders (name, chat_id) VALUES (?, ?)", (name, chat_id))
        conn.commit()
        return cur.lastrowid
    except Exception as e:
        print("创建文件夹失败：", e)
        return None

# 获取用户所有文件夹
def get_user_folders(chat_id):
    cur.execute("SELECT * FROM folders WHERE chat_id = ?", (chat_id,))
    return cur.fetchall()

# 保存文件到文件夹
def save_file(folder_id, file_id, file_type="photo", caption=""):
    cur.execute('''
    INSERT INTO files (folder_id, file_id, file_type, caption)
    VALUES (?, ?, ?, ?)
    ''', (folder_id, file_id, file_type, caption))
    conn.commit()

# 获取文件夹里的所有文件
def get_files_in_folder(folder_id):
    cur.execute("SELECT * FROM files WHERE folder_id = ?", (folder_id,))
    return cur.fetchall()

# 通过文件夹名+chat_id获取文件夹ID
def get_folder_id_by_name(name, chat_id):
    cur.execute("SELECT id FROM folders WHERE name = ? AND chat_id = ?", (name, chat_id))
    row = cur.fetchone()
    return row[0] if row else None
