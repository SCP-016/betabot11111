import os
import time
import telebot
from telebot import types
import pg8000.dbapi
from urllib.parse import urlparse

# ==================== 环境变量 ====================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
DATABASE_URL = os.environ.get("DATABASE_URL")

bot = telebot.TeleBot(BOT_TOKEN, parse_mode=None)
user_temp = {}
pending_media = {}
current_save_folder = None

# ==================== Postgres 连接 ====================
def get_db():
    try:
        url = urlparse(DATABASE_URL)
        conn = pg8000.dbapi.connect(
            user=url.username,
            password=url.password,
            host=url.hostname,
            port=url.port,
            database=url.path[1:],
            timeout=10
        )
        return conn
    except Exception as e:
        print("数据库连接失败:", e)
        return None

def init_db():
    try:
        conn = get_db()
        if not conn:
            return
        cur = conn.cursor()
        cur.execute('''
        CREATE TABLE IF NOT EXISTS folders (
            id SERIAL PRIMARY KEY,
            name TEXT UNIQUE NOT NULL
        )
        ''')
        cur.execute('''
        CREATE TABLE IF NOT EXISTS media (
            id SERIAL PRIMARY KEY,
            file_id TEXT NOT NULL,
            file_type TEXT NOT NULL,
            folder_id INTEGER REFERENCES folders(id) ON DELETE CASCADE
        )
        ''')
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print("初始化表错误:", e)

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
    global current_save_folder
    current_save_folder = None
    try:
        text = "📸 媒体分类机器人\n" \
               "▸ 打开文件夹自动设为默认存储目录\n" \
               "▸ 收到视频/图片自动存入当前默认文件夹\n\n" \
               "可用指令：\n" \
               "/setfolder - 查看当前默认文件夹\n" \
               "/clearfolder - 取消默认文件夹\n" \
               "/getallvideo - 取出默认文件夹全部视频（不含图片）"
        bot.send_message(message.chat.id, text, reply_markup=main_menu())
    except:
        pass

# 查看当前默认文件夹
@bot.message_handler(commands=["setfolder"])
def cmd_setfolder(message):
    global current_save_folder
    if not current_save_folder:
        bot.send_message(message.chat.id, "⚠️ 当前未设置默认存储文件夹，请先打开任意文件夹")
        return
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT name FROM folders WHERE id=%s", (current_save_folder,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        bot.send_message(message.chat.id, f"✅ 当前默认存储文件夹：{row[0]}")
    except:
        bot.send_message(message.chat.id, "❌ 查询失败")

# 取消默认文件夹
@bot.message_handler(commands=["clearfolder"])
def cmd_clearfolder(message):
    global current_save_folder
    current_save_folder = None
    bot.send_message(message.chat.id, "✅ 已取消默认存储文件夹，媒体不再自动保存")

# 取出默认文件夹所有视频（保留原有逻辑，只发视频）
@bot.message_handler(commands=["getallvideo"])
def cmd_getallvideo(message):
    global current_save_folder
    if not current_save_folder:
        bot.send_message(message.chat.id, "⚠️ 请先设置默认存储文件夹")
        return
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT file_id FROM media WHERE folder_id=%s AND file_type='video'", (current_save_folder,))
        videos = cur.fetchall()
        cur.close()
        conn.close()
        if not videos:
            bot.send_message(message.chat.id, "❌ 默认文件夹内暂无视频")
            return
        bot.send_message(message.chat.id, f"🎬 开始发送全部 {len(videos)} 个视频...")
        for v in videos:
            try:
                bot.send_video(message.chat.id, v[0])
                time.sleep(0.6)
            except:
                continue
        bot.send_message(message.chat.id, "✅ 全部视频发送完毕")
    except:
        bot.send_message(message.chat.id, "❌ 发送失败")

# ==================== 文件夹列表 ====================
def list_folders_msg(chat_id):
    global current_save_folder
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT id, name FROM folders")
        folders = cur.fetchall()
        cur.close()
        conn.close()

        kb = types.InlineKeyboardMarkup(row_width=1)
        if not folders:
            bot.send_message(chat_id, "❌ 暂无文件夹", reply_markup=main_menu())
            return

        for f in folders:
            mark = "【默认】" if current_save_folder == f[0] else ""
            kb.add(types.InlineKeyboardButton(f"{mark}📁 {f[1]}", callback_data=f"open_{f[0]}"))
        kb.add(types.InlineKeyboardButton("🔙 返回", callback_data="back_main"))
        bot.send_message(chat_id, "📂 文件夹列表（打开即设为默认保存目录）", reply_markup=kb)
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

# ==================== 打开文件夹（设为默认存储）====================
@bot.callback_query_handler(func=lambda c: c.data.startswith("open_"))
def open_folder(call):
    global current_save_folder
    try:
        bot.answer_callback_query(call.id)
        fid = call.data.split("_")[1]
        current_save_folder = fid

        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT name FROM folders WHERE id=%s", (fid,))
        folder = cur.fetchone()
        name = folder[0]

        cur.execute("SELECT id, file_type FROM media WHERE folder_id=%s", (fid,))
        media = cur.fetchall()
        cur.close()
        conn.close()

        kb = types.InlineKeyboardMarkup(row_width=2)
        for m in media:
            icon = "🖼️" if m[1] == "photo" else "🎥"
            kb.row(
                types.InlineKeyboardButton(f"{icon} 媒体", callback_data=f"show_{m[0]}"),
                types.InlineKeyboardButton("🗑️ 删除", callback_data=f"delm_{m[0]}")
            )
        # 修改按钮文字，说明会同时发图片+视频
        kb.add(types.InlineKeyboardButton("🖼️🎬 一次性发送全部图片+视频", callback_data=f"send_all_video_{fid}"))
        kb.add(
            types.InlineKeyboardButton("✏️ 重命名", callback_data=f"ren_{fid}"),
            types.InlineKeyboardButton("🗑️ 删除文件夹", callback_data=f"delf_{fid}")
        )
        kb.add(types.InlineKeyboardButton("🔙 返回", callback_data="list_folders"))

        bot.edit_message_text(f"📁 {name}\n✅ 已设为默认存储文件夹，图片/视频将自动存入", call.message.chat.id, call.message.id, reply_markup=kb)
    except:
        pass

# 按钮取出当前文件夹全部图片+视频（修改核心逻辑）
@bot.callback_query_handler(func=lambda c: c.data.startswith("send_all_video_"))
def send_all_video_btn(call):
    try:
        bot.answer_callback_query(call.id)
        fid = call.data.split("_")[-1]
        conn = get_db()
        cur = conn.cursor()
        # 去掉 file_type='video'，查询该文件夹所有媒体（图片+视频）
        cur.execute("SELECT file_id, file_type FROM media WHERE folder_id=%s", (fid,))
        all_media = cur.fetchall()
        cur.close()
        conn.close()
        if not all_media:
            bot.send_message(call.message.chat.id, "❌ 该文件夹暂无图片和视频")
            return
        bot.send_message(call.message.chat.id, f"🖼️🎬 开始发送 {len(all_media)} 个媒体（图片+视频）...")
        for item in all_media:
            file_id, ftype = item
            try:
                if ftype == "photo":
                    bot.send_photo(call.message.chat.id, file_id)
                else:
                    bot.send_video(call.message.chat.id, file_id)
                time.sleep(0.6)
            except Exception as e:
                print("发送单个媒体失败：", e)
                continue
        bot.send_message(call.message.chat.id, "✅ 全部图片、视频发送完成")
    except Exception as e:
        print("批量发送媒体报错：", e)
        bot.send_message(call.message.chat.id, "❌ 发送失败")

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
        conn = get_db()
        cur = conn.cursor()
        cur.execute("INSERT INTO folders (name) VALUES (%s)", (name,))
        conn.commit()
        cur.close()
        conn.close()
        bot.send_message(message.chat.id, f"✅ 文件夹「{name}」创建成功", reply_markup=main_menu())
        del user_temp[message.from_user.id]
    except:
        pass

# ==================== 重命名文件夹 ====================
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
        conn = get_db()
        cur = conn.cursor()
        cur.execute("UPDATE folders SET name=%s WHERE id=%s", (name, fid))
        conn.commit()
        cur.close()
        conn.close()
        bot.send_message(message.chat.id, f"✅ 已重命名为「{name}」", reply_markup=main_menu())
        del user_temp[message.from_user.id]
    except:
        pass

# ==================== 接收图片/视频 自动保存 ====================
@bot.message_handler(content_types=["photo", "video"])
def save_media(message):
    global current_save_folder
    try:
        if message.photo:
            file_id = message.photo[-1].file_id
            typ = "photo"
        else:
            file_id = message.video.file_id
            typ = "video"

        if current_save_folder:
            conn = get_db()
            cur = conn.cursor()
            cur.execute("INSERT INTO media (file_id, file_type, folder_id) VALUES (%s, %s, %s)", (file_id, typ, current_save_folder))
            conn.commit()
            cur.close()
            conn.close()
            bot.send_message(message.chat.id, "✅ 已自动存入默认文件夹")
            return

        pending_media[message.from_user.id] = {"fid": file_id, "type": typ}
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT id, name FROM folders")
        folders = cur.fetchall()
        cur.close()
        conn.close()

        if not folders:
            bot.send_message(message.chat.id, "❌ 请先创建文件夹", reply_markup=main_menu())
            return

        kb = types.InlineKeyboardMarkup(row_width=1)
        for f in folders:
            kb.add(types.InlineKeyboardButton(f"📁 {f[1]}", callback_data=f"sel_{f[0]}"))
        bot.send_message(message.chat.id, "✅ 请选择保存文件夹", reply_markup=kb)
    except Exception as e:
        print(f"保存媒体错误: {e}")

@bot.callback_query_handler(func=lambda c: c.data.startswith("sel_"))
def confirm_save(call):
    try:
        bot.answer_callback_query(call.id)
        folder_id = call.data.split("_")[1]
        user_id = call.from_user.id

        if user_id not in pending_media:
            bot.edit_message_text("❌ 媒体已过期", call.message.chat.id, call.message.id, reply_markup=main_menu())
            return

        data = pending_media[user_id]
        file_id = data["fid"]
        typ = data["type"]

        conn = get_db()
        cur = conn.cursor()
        cur.execute("INSERT INTO media (file_id, file_type, folder_id) VALUES (%s, %s, %s)", (file_id, typ, folder_id))
        conn.commit()
        cur.close()
        conn.close()

        del pending_media[user_id]
        bot.edit_message_text("✅ 保存成功", call.message.chat.id, call.message.id, reply_markup=main_menu())
    except:
        pass

# ==================== 删除媒体（二次确认）====================
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
        conn = get_db()
        cur = conn.cursor()
        cur.execute("DELETE FROM media WHERE id=%s", (mid,))
        conn.commit()
        cur.close()
        conn.close()
        bot.edit_message_text("🗑️ 已删除", call.message.chat.id, call.message.id, reply_markup=main_menu())
    except:
        pass

# ==================== 删除文件夹（二次确认）====================
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
    global current_save_folder
    try:
        bot.answer_callback_query(call.id)
        fid = call.data.split("_")[1]
        if current_save_folder == fid:
            current_save_folder = None

        conn = get_db()
        cur = conn.cursor()
        cur.execute("DELETE FROM media WHERE folder_id=%s", (fid,))
        cur.execute("DELETE FROM folders WHERE id=%s", (fid,))
        conn.commit()
        cur.close()
        conn.close()

        bot.edit_message_text("🗑️ 文件夹已删除", call.message.chat.id, call.message.id, reply_markup=main_menu())
    except:
        pass

# ==================== 返回主菜单 ====================
@bot.callback_query_handler(func=lambda c: c.data == "back_main")
def back_main(call):
    try:
        bot.answer_callback_query(call.id)
        bot.edit_message_text("📸 媒体分类机器人", call.message.chat.id, call.message.id, reply_markup=main_menu())
    except:
        pass

# ==================== 24小时稳定运行 ====================
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
