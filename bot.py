import os
import time
import telebot
from telebot import types
import libsql_client

# ==================== 环境变量 ====================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
TURSO_URL = os.environ.get("TURSO_DATABASE_URL")
TURSO_TOKEN = os.environ.get("TURSO_AUTH_TOKEN")

bot = telebot.TeleBot(BOT_TOKEN)
user_temp = {}  # 临时存储用户操作

# ==================== 数据库 ====================
def get_db():
    return libsql_client.create_client_sync(TURSO_URL, auth_token=TURSO_TOKEN)

def init_db():
    db = get_db()
    db.execute('''CREATE TABLE IF NOT EXISTS folders
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE)''')
    db.execute('''CREATE TABLE IF NOT EXISTS media
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, file_id TEXT, file_type TEXT, folder_id INTEGER)''')
    db.close()

# ==================== 菜单 ====================
def main_menu():
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("📁 我的文件夹", callback_data="list_folders"))
    kb.add(types.InlineKeyboardButton("➕ 创建文件夹", callback_data="create_folder"))
    return kb

# ==================== /start ====================
@bot.message_handler(commands=["start"])
def start(message):
    bot.send_message(message.chat.id, "📸 媒体分类机器人\n转发图片/视频即可保存", reply_markup=main_menu())

# ==================== 文件夹列表 ====================
def list_folders_msg(chat_id):
    db = get_db()
    folders = db.execute("SELECT * FROM folders").rows
    db.close()
    kb = types.InlineKeyboardMarkup()
    if not folders:
        bot.send_message(chat_id, "❌ 暂无文件夹", reply_markup=main_menu())
        return
    for f in folders:
        kb.add(types.InlineKeyboardButton(f"📁 {f[1]}", callback_data=f"open_{f[0]}"))
    kb.add(types.InlineKeyboardButton("🔙 返回", callback_data="back_main"))
    bot.send_message(chat_id, "📂 文件夹列表", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data == "list_folders")
def list_folders(call):
    bot.answer_callback_query(call.id)
    list_folders_msg(call.message.chat.id)
    bot.delete_message(call.message.chat.id, call.message.id)

# ==================== 打开文件夹 ====================
@bot.callback_query_handler(func=lambda c: c.data.startswith("open_"))
def open_folder(call):
    bot.answer_callback_query(call.id)
    fid = call.data.split("_")[1]
    db = get_db()
    name = db.execute("SELECT name FROM folders WHERE id=?", [fid]).rows[0][0]
    media = db.execute("SELECT id,file_type FROM media WHERE folder_id=?", [fid]).rows
    db.close()

    kb = types.InlineKeyboardMarkup()
    for m in media:
        icon = "🖼️" if m[1] == "photo" else "🎥"
        kb.row(
            types.InlineKeyboardButton(f"{icon} 媒体", callback_data=f"show_{m[0]}"),
            types.InlineKeyboardButton("🗑️ 删除", callback_data=f"delm_{m[0]}")
        )
    kb.add(types.InlineKeyboardButton("🎬 取出所有视频", callback_data=f"getallv_{fid}"))
    kb.add(types.InlineKeyboardButton("✏️ 重命名", callback_data=f"ren_{fid}"))
    kb.add(types.InlineKeyboardButton("🗑️ 删除文件夹", callback_data=f"delf_{fid}"))
    kb.add(types.InlineKeyboardButton("🔙 返回", callback_data="list_folders"))

    bot.edit_message_text(f"📁 {name}", call.message.chat.id, call.message.id, reply_markup=kb)

# ==================== 创建文件夹 ====================
@bot.callback_query_handler(func=lambda c: c.data == "create_folder")
def create_folder(call):
    bot.answer_callback_query(call.id)
    user_temp[call.from_user.id] = {"act": "create"}
    bot.edit_message_text("✏️ 请直接发送文件夹名称", call.message.chat.id, call.message.id)

@bot.message_handler(func=lambda m: m.from_user.id in user_temp and user_temp[m.from_user.id]["act"] == "create")
def create_done(message):
    name = message.text.strip()
    db = get_db()
    db.execute("INSERT INTO folders (name) VALUES (?)", [name])
    db.close()
    bot.send_message(message.chat.id, f"✅ 文件夹「{name}」创建成功", reply_markup=main_menu())
    del user_temp[message.from_user.id]

# ==================== 重命名 ====================
@bot.callback_query_handler(func=lambda c: c.data.startswith("ren_"))
def rename(call):
    bot.answer_callback_query(call.id)
    user_temp[call.from_user.id] = {"act": "rename", "fid": call.data.split("_")[1]}
    bot.edit_message_text("✏️ 发送新名称", call.message.chat.id, call.message.id)

@bot.message_handler(func=lambda m: m.from_user.id in user_temp and user_temp[m.from_user.id]["act"] == "rename")
def rename_done(message):
    name = message.text.strip()
    fid = user_temp[message.from_user.id]["fid"]
    db = get_db()
    db.execute("UPDATE folders SET name=? WHERE id=?", [name, fid])
    db.close()
    bot.send_message(message.chat.id, f"✅ 已重命名为「{name}」", reply_markup=main_menu())
    del user_temp[message.from_user.id]

# ==================== 保存媒体 ====================
@bot.message_handler(content_types=["photo", "video"])
def save_media(message):
    file_id, typ = (message.photo[-1].file_id, "photo") if message.photo else (message.video.file_id, "video")
    db = get_db()
    folders = db.execute("SELECT id,name FROM folders").rows
    db.close()
    if not folders:
        bot.send_message(message.chat.id, "❌ 请先创建文件夹", reply_markup=main_menu())
        return
    kb = types.InlineKeyboardMarkup()
    for f in folders:
        kb.add(types.InlineKeyboardButton(f"📁 {f[1]}", callback_data=f"save_{file_id}_{typ}_{f[0]}"))
    bot.send_message(message.chat.id, "✅ 保存到：", reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("save_"))
def confirm_save(call):
    bot.answer_callback_query(call.id)
    _, fid, typ, folder_id = call.data.split("_")
    db = get_db()
    db.execute("INSERT INTO media (file_id,file_type,folder_id) VALUES (?,?,?)", [fid, typ, folder_id])
    db.close()
    bot.edit_message_text("✅ 保存成功", call.message.chat.id, call.message.id, reply_markup=main_menu())

# ==================== 取出所有视频 ====================
@bot.callback_query_handler(func=lambda c: c.data.startswith("getallv_"))
def get_all_videos(call):
    bot.answer_callback_query(call.id)
    fid = call.data.split("_")[1]
    db = get_db()
    videos = db.execute("SELECT file_id FROM media WHERE folder_id=? AND file_type='video'", [fid]).rows
    db.close()
    if not videos:
        bot.send_message(call.message.chat.id, "❌ 该文件夹无视频")
        return
    bot.send_message(call.message.chat.id, f"🎬 正在发送 {len(videos)} 个视频…")
    for v in videos:
        try:
            bot.send_video(call.message.chat.id, v[0])
            time.sleep(0.5)
        except:
            continue
    bot.send_message(call.message.chat.id, "✅ 发送完成")

# ==================== 删除媒体 ====================
@bot.callback_query_handler(func=lambda c: c.data.startswith("delm_"))
def ask_del_media(call):
    bot.answer_callback_query(call.id)
    mid = call.data.split("_")[1]
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("✅ 确认删除", callback_data=f"confdelm_{mid}"))
    kb.add(types.InlineKeyboardButton("🔙 取消", callback_data="back_main"))
    bot.edit_message_text("⚠️ 确定删除此媒体？", call.message.chat.id, call.message.id, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("confdelm_"))
def do_del_media(call):
    bot.answer_callback_query(call.id)
    mid = call.data.split("_")[1]
    db = get_db()
    db.execute("DELETE FROM media WHERE id=?", [mid])
    db.close()
    bot.edit_message_text("🗑️ 已删除", call.message.chat.id, call.message.id, reply_markup=main_menu())

# ==================== 删除文件夹 ====================
@bot.callback_query_handler(func=lambda c: c.data.startswith("delf_"))
def ask_del_folder(call):
    bot.answer_callback_query(call.id)
    fid = call.data.split("_")[1]
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("✅ 确认删除", callback_data=f"confdelf_{fid}"))
    kb.add(types.InlineKeyboardButton("🔙 取消", callback_data="list_folders"))
    bot.edit_message_text("⚠️ 删除会清空所有媒体！确定？", call.message.chat.id, call.message.id, reply_markup=kb)

@bot.callback_query_handler(func=lambda c: c.data.startswith("confdelf_"))
def do_del_folder(call):
    bot.answer_callback_query(call.id)
    fid = call.data.split("_")[1]
    db = get_db()
    db.execute("DELETE FROM media WHERE folder_id=?", [fid])
    db.execute("DELETE FROM folders WHERE id=?", [fid])
    db.close()
    bot.edit_message_text("🗑️ 文件夹已删除", call.message.chat.id, call.message.id, reply_markup=main_menu())

# ==================== 返回 ====================
@bot.callback_query_handler(func=lambda c: c.data == "back_main")
def back_main(call):
    bot.answer_callback_query(call.id)
    bot.edit_message_text("📸 媒体分类机器人", call.message.chat.id, call.message.id, reply_markup=main_menu())

# ==================== 24h 自动重连（防掉线）====================
def run():
    init_db()
    print("✅ 机器人启动成功 | Railway 24h 运行中")
    while True:
        try:
            bot.infinity_polling(timeout=60)
        except Exception as e:
            print(f"⚠️ 异常：{e}，10秒后重连")
            time.sleep(10)

if __name__ == "__main__":
    run()
