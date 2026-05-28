import os
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters
)
import libsql_client

# 初始化数据库
async def init_db():
    url = os.getenv("TURSO_DATABASE_URL")
    token = os.getenv("TURSO_AUTH_TOKEN")
    client = libsql_client.create_client_sync(url, auth_token=token)

    client.execute('''
        CREATE TABLE IF NOT EXISTS folders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        )
    ''')

    client.execute('''
        CREATE TABLE IF NOT EXISTS media (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id TEXT NOT NULL,
            file_type TEXT NOT NULL,
            folder_id INTEGER NOT NULL,
            FOREIGN KEY (folder_id) REFERENCES folders(id)
        )
    ''')
    client.close()

# —————— 工具函数 ——————
def get_db():
    url = os.getenv("TURSO_DATABASE_URL")
    token = os.getenv("TURSO_AUTH_TOKEN")
    return libsql_client.create_client_sync(url, auth_token=token)

# —————— 菜单 ——————
def main_menu():
    keyboard = [
        [InlineKeyboardButton("📁 我的文件夹", callback_data="list_folders")],
        [InlineKeyboardButton("➕ 创建文件夹", callback_data="create_folder")],
    ]
    return InlineKeyboardMarkup(keyboard)

# —————— 启动命令 ——————
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📸 媒体分类机器人\n转发图片/视频即可保存",
        reply_markup=main_menu()
    )

# —————— 文件夹列表 ——————
async def list_folders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    db = get_db()
    folders = db.execute("SELECT * FROM folders").rows
    db.close()

    if not folders:
        await query.edit_message_text("❌ 无文件夹", reply_markup=main_menu())
        return

    keyboard = []
    for f in folders:
        keyboard.append([InlineKeyboardButton(f"📁 {f[1]}", callback_data=f"open_{f[0]}")])
    keyboard.append([InlineKeyboardButton("🔙 返回", callback_data="back_main")])
    await query.edit_message_text("📂 文件夹列表", reply_markup=InlineKeyboardMarkup(keyboard))

# —————— 打开文件夹 ——————
async def open_folder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    fid = query.data.split("_")[1]
    db = get_db()
    folder = db.execute("SELECT name FROM folders WHERE id = ?", [fid]).rows[0][0]
    media = db.execute("SELECT id,file_type FROM media WHERE folder_id = ?", [fid]).rows
    db.close()

    keyboard = []
    for m in media:
        keyboard.append([
            InlineKeyboardButton(f"🗑️ 删除", callback_data=f"delm_{m[0]}"),
            InlineKeyboardButton(f"📎 查看", callback_data=f"show_{m[0]}")
        ])
    keyboard.extend([
        [InlineKeyboardButton("🗑️ 删除文件夹", callback_data=f"delf_{fid}")],
        [InlineKeyboardButton("✏️ 重命名", callback_data=f"ren_{fid}")],
        [InlineKeyboardButton("🔙 返回", callback_data="list_folders")]
    ])
    await query.edit_message_text(f"📁 {folder}", reply_markup=InlineKeyboardMarkup(keyboard))

# —————— 接收媒体 ——————
async def save_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    file_id = None
    typ = None

    if msg.photo:
        file_id = msg.photo[-1].file_id
        typ = "photo"
    elif msg.video:
        file_id = msg.video.file_id
        typ = "video"
    else:
        return

    db = get_db()
    folders = db.execute("SELECT * FROM folders").rows
    if not folders:
        await msg.reply_text("❌ 先创建文件夹")
        return

    keyboard = []
    for f in folders:
        keyboard.append([InlineKeyboardButton(f"📁 {f[1]}", callback_data=f"save_{file_id}_{typ}_{f[0]}")])
    await msg.reply_text("✅ 选择保存到：", reply_markup=InlineKeyboardMarkup(keyboard))

# —————— 确认保存 ——————
async def confirm_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, fid, typ, folder = query.data.split("_")
    db = get_db()
    db.execute("INSERT INTO media (file_id, file_type, folder_id) VALUES (?,?,?)", [fid, typ, folder])
    db.close()
    await query.edit_message_text("✅ 已保存")

# —————— 删除确认（防误触）——————
async def ask_delete_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    mid = query.data.split("_")[1]
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("✅ 确认删除", callback_data=f"confdelm_{mid}")],
        [InlineKeyboardButton("🔙 取消", callback_data="back_main")]
    ]
    await query.edit_message_text("⚠️ 确定删除？", reply_markup=InlineKeyboardMarkup(keyboard))

async def delete_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    mid = query.data.split("_")[1]
    db = get_db()
    db.execute("DELETE FROM media WHERE id = ?", [mid])
    db.close()
    await query.edit_message_text("🗑️ 已删除")

# —————— 路由 ——————
def main():
    token = os.getenv("BOT_TOKEN")
    app = ApplicationBuilder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO, save_media))

    app.add_handler(CallbackQueryHandler(list_folders, pattern="^list_folders$"))
    app.add_handler(CallbackQueryHandler(open_folder, pattern="^open_"))
    app.add_handler(CallbackQueryHandler(confirm_save, pattern="^save_"))
    app.add_handler(CallbackQueryHandler(ask_delete_media, pattern="^delm_"))
    app.add_handler(CallbackQueryHandler(delete_media, pattern="^confdelm_"))
    app.add_handler(CallbackQueryHandler(lambda u,c: u.callback_query.edit_message_text(reply_markup=main_menu()), pattern="^back_main$"))

    app.run_polling()

if __name__ == "__main__":
    asyncio.run(init_db())
    main()
