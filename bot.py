import os
import time
import telebot
from telebot import types
import sqlite3

# ==================== 环境变量 ====================
BOT_TOKEN = os.environ.get("BOT_TOKEN")

bot = telebot.TeleBot(BOT_TOKEN, parse_mode=None)
user_temp = {}

# ==================== 数据库 ====================
def get_db():
    conn = sqlite3.connect("/app/bot.db")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    db = get_db()
    db.execute('''CREATE TABLE IF NOT EXISTS folders
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE)''')
    db.execute('''CREATE TABLE IF NOT EXISTS media
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, file_id TEXT, file_type TEXT, folder_id INTEGER)''')
    db.commit()
    db.close()

# ==================== 菜单 ====================
def main_menu():
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("📁 我的文件夹", callback_data="list_folders"),
        types.InlineKeyboardButton("➕ 创建文件夹", callback_data="create_folder")
    )
    return kb

# ==================== /start ====================
@bot.message_handler(commands=["start"])
def start(message):
    try:
        bot.send_message(message.chat.id, "📸 媒体分类机器人\n转发图片/视频即可保存", reply_markup=main_menu())
    except:
        pass

# ==================== 文件夹列表 ====================
def list_folders_msg(chat_id):
    try:
        db = get_db()
        folders = db.execute("SELECT * FROM folders").fetchall()
        db.close()

        kb = types.InlineKeyboardMarkup(row_width=1)
        if not folders:
            bot.send_message(chat_id, "❌ 暂无文件夹", reply_markup=main_menu())
            return

        for f in folders:
            kb.add(types.InlineKeyboardButton(f"📁 {f['name']}", callback_data=f"open_{f['id']}"))
        kb.add(types.InlineKeyboardButton("🔙 返回", callback_data="back_main"))
        bot.send_message(chat_id, "📂 文件夹列表", reply_markup=kb)
    except:
        pass

@bot.callback_query_handler(func=lambda c: c.data == "list_folders")
def list_folders(call):
    try:
        bot.answer_callback_query(call.id)
        list_folders_msg(call.message.chat.id)
        bot.delete_message(call.message.chat.id, call.message.id)
    except:
        pass

# ==================== 打开文件夹 ====================
@bot.callback_query_handler(func=lambda c: c.data.startswith("open_"))
def open_folder(call):
    try:
        bot.answer_callback_query(call.id)
        fid = call.data.split("_")[1]
        db = get_db()
        folder = db.execute("SELECT name FROM folders WHERE id=?", [fid]).fetchone()
        name = folder['name']
        media = db.execute("SELECT id,file_type FROM media WHERE folder_id=?", [fid]).fetchall()
        db.close()

        kb = types.InlineKeyboardMarkup(row_width=2)
        for m in media:
            icon = "🖼️" if m['file_type'] == "photo" else "🎥"
            kb.row(
                types.InlineKeyboardButton(f"{icon} 媒体", callback_data=f"show_{m['id']}"),
                types.InlineKeyboardButton("🗑️ 删除", callback_data=f"delm_{m['id']}")
            )
        kb.add(types.InlineKeyboardButton("🎬 取出所有视频", callback_data=f"getallv_{fid}"))
        kb.add(
            types.InlineKeyboardButton("✏️ 重命名", callback_data=f"ren_{fid}"),
            types.InlineKeyboardButton("🗑️ 删除文件夹", callback_data=f"delf_{fid}")
        )
        kb.add(types.InlineKeyboardButton("🔙 返回", callback_data="list_folders"))

        bot.edit_message_text(f"📁 {name}", call.message.chat.id, call.message.id, reply_markup=kb)
    except:
        pass

# ==================== 创建文件夹 ====================
@bot.callback_query_handler(func=lambda c: c.data == "create_folder")
def create_folder(call):
    try:
        bot.answer_callback_query(call.id)
        user_temp[call.from_user.id] = {"act": "create"}
        bot.edit_message_text("✏️ 请直接发送文件夹名称", call.message.chat.id, call.message.id)
    except:
        pass

@bot.message_handler(func=lambda m: m.from_user.id in user_temp and user_temp[m.from_user.id]["act"] == "create")
def create_done(message):
    try:
        name = message.text.strip()
        db = get_db()
        db.execute("INSERT INTO folders (name) VALUES (?)", [name])
        db.commit()
        db.close()
        bot.send_message(message.chat.id, f"✅ 文件夹「{name}」创建成功", reply_markup=main_menu())
        del user_temp[message.from_user.id]
    except:
        pass

# ==================== 重命名 ====================
@bot.callback_query_handler(func=lambda c: c.data.startswith("ren_"))
def rename(call):
    try:
        bot.answer_callback_query(call.id)
        user_temp[call.from_user.id] = {"act": "rename", "fid": call.data.split("_")[1]}
        bot.edit_message_text("✏️ 发送新名称", call.message.chat.id, call.message.id)
    except:
        pass

@bot.message_handler(func=lambda m: m.from_user.id in user_temp and user_temp[m.from_user.id]["act"] == "rename")
def rename_done(message):
    try:
        name = message.text.strip()
        fid = user_temp[message.from_user.id]["fid"]
        db = get_db()
        db.execute("UPDATE folders SET name=? WHERE id=?", [name, fid])
        db.commit()
        db.close()
        bot.send_message(message.chat.id, f"✅ 已重命名为「{name}」", reply_markup=main_menu())
        del user_temp[message.from_user.id]
    except:
        pass

# ==================== 保存媒体 ====================
@bot.message_handler(content_types=["photo", "video"])
def save_media(message):
    try:
        if message.photo:
            file_id = message.photo[-1].file_id
            typ = "photo"
        else:
            file_id = message.video.file_id
            typ = "video"

        db = get_db()
        folders = db.execute("SELECT id,name FROM folders").fetchall()
        db.close()

        if not folders:
            bot.send_message(message.chat.id, "❌ 请先创建文件夹", reply_markup=main_menu())
            return

        kb = types.InlineKeyboardMarkup(row_width=1)
        for f in folders:
            kb.add(types.InlineKeyboardButton(f"📁 {f['name']}", callback_data=f"save_{file_id}_{typ}_{f['id']}"))
        
        bot.send_message(message.chat.id, "✅ 保存到：", reply_markup=kb)
    except Exception as e:
        print(f"保存媒体错误: {e}")

@bot.callback_query_handler(func=lambda c: c.data.startswith("save_"))
def confirm_save(call):
    try:
        bot.answer_callback_query(call.id)
        parts = call.data.split("_")
        fid = parts[1]
        typ = parts[2]
        folder_id = parts[3]

        db = get_db()
        db.execute("INSERT INTO media (file_id,file_type,folder_id) VALUES (?,?,?)", [fid, typ, folder_id])
        db.commit()
        db.close()
        bot.edit_message_text("✅ 保存成功", call.message.chat.id, call.message.id, reply_markup=main_menu())
    except:
        pass

# ==================== 取出所有视频 ====================
@bot.callback_query_handler(func=lambda c: c.data.startswith("getallv_"))
def get_all_videos(call):
    try:
        bot.answer_callback_query(call.id)
        fid = call.data.split("_")[1]
        db = get_db()
        videos = db.execute("SELECT file_id FROM media WHERE folder_id=? AND file_type='video'", [fid]).fetchall()
        db.close()

        if not videos:
            bot.send_message(call.message.chat.id, "❌ 该文件夹无视频")
            return

        bot.send_message(call.message.chat.id, f"🎬 正在发送 {len(videos)} 个视频…")
        for v in videos:
            try:
                bot.send_video(call.message.chat.id, v['file_id'])
                time.sleep(0.6)
            except:
                continue
        bot.send_message(call.message.chat.id, "✅ 发送完成")
    except:
        pass

# ==================== 删除媒体 ====================
@bot.callback_query_handler(func=lambda c: c.data.startswith("delm_"))
def ask_del_media(call):
    try:
        bot.answer_callback_query(call.id)
        mid = call.data.split("_")[1]
        kb = types.InlineKeyboardMarkup(row_width=1)
        kb.add(types.InlineKeyboardButton("✅ 确认删除", callback_data=f"confdelm_{mid}"))
        kb.add(types.InlineKeyboardButton("🔙 取消", callback_data="back_main"))
        bot.edit_message_text("⚠️ 确定删除此媒体？", call.message.chat.id, call.message.id, reply_markup=kb)
    except:
        pass

@bot.callback_query_handler(func=lambda c: c.data.startswith("confdelm_"))
def do_del_media(call):
    try:
        bot.answer_callback_query(call.id)
        mid = call.data.split("_")[1]
        db = get_db()
        db.execute("DELETE FROM media WHERE id=?", [mid])
        db.commit()
        db.close()
        bot.edit_message_text("🗑️ 已删除", call.message.chat.id, call.message.id, reply_markup=main_menu())
    except:
        pass

# ==================== 删除文件夹 ====================
@bot.callback_query_handler(func=lambda c: c.data.startswith("delf_"))
def ask_del_folder(call):
    try:
        bot.answer_callback_query(call.id)
        fid = call.data.split("_")[1]
        kb = types.InlineKeyboardMarkup(row_width=1)
        kb.add(types.InlineKeyboardButton("✅ 确认删除", callback_data=f"confdelf_{fid}"))
        kb.add(types.InlineKeyboardButton("🔙 取消", callback_data="list_folders"))
        bot.edit_message_text("⚠️ 删除会清空所有媒体！确定？", call.message.chat.id, call.message.id, reply_markup=kb)
    except:
        pass

@bot.callback_query_handler(func=lambda c: c.data.startswith("confdelf_"))
def do_del_folder(call):
    try:
        bot.answer_callback_query(call.id)
        fid = call.data.split("_")[1]
        db = get_db()
        db.execute("DELETE FROM media WHERE folder_id=?", [fid])
        db.execute("DELETE FROM folders WHERE id=?", [fid])
        db.commit()
        db.close()
        bot.edit_message_text("🗑️ 文件夹已删除", call.message.chat.id, call.message.id, reply_markup=main_menu())
    except:
        pass

# ==================== 返回 ====================
@bot.callback_query_handler(func=lambda c: c.data == "back_main")
def back_main(call):
    try:
        bot.answer_callback_query(call.id)
        bot.edit_message_text("📸 媒体分类机器人", call.message.chat.id, call.message.id, reply_markup=main_menu())
    except:
        pass

# ==================== 24h 运行 ====================
def run():
    init_db()
    print("✅ 机器人启动成功 - 24小时运行中")
    while True:
        try:
            bot.infinity_polling(timeout=60, skip_pending=True)
        except Exception as e:
            print(f"重启中: {e}")
            time.sleep(10)

if __name__ == "__main__":
    run()
