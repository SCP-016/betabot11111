import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ConversationHandler, filters, ContextTypes
)
from database import Database

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Conversation states
WAITING_FOLDER_NAME = 1
WAITING_RENAME_NAME = 2
WAITING_CLASSIFY_CHOICE = 3

db = Database()

# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def main_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📁 查看所有文件夹", callback_data="list_folders")],
        [
            InlineKeyboardButton("➕ 新建文件夹", callback_data="create_folder"),
            InlineKeyboardButton("✏️ 重命名", callback_data="rename_folder"),
        ],
        [InlineKeyboardButton("🗑️ 删除文件夹", callback_data="delete_folder_menu")],
    ])

def folders_keyboard(action_prefix: str, include_back=True):
    """Build folder selection keyboard for a given action."""
    folders = db.get_all_folders()
    if not folders:
        return None
    rows = []
    for f in folders:
        count = db.count_media(f["id"])
        rows.append([InlineKeyboardButton(
            f"📁 {f['name']}  ({count}个文件)",
            callback_data=f"{action_prefix}:{f['id']}"
        )])
    if include_back:
        rows.append([InlineKeyboardButton("🔙 返回主菜单", callback_data="main_menu")])
    return InlineKeyboardMarkup(rows)

async def send_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, text="请选择操作："):
    kb = main_menu_keyboard()
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=kb)
    else:
        await update.message.reply_text(text, reply_markup=kb)

# ─────────────────────────────────────────────
# /start
# ─────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_main_menu(update, context, "👋 欢迎使用媒体管理机器人！\n\n直接发送图片或视频，我会帮你分类整理。")

# ─────────────────────────────────────────────
# Receive media (photo / video / document)
# ─────────────────────────────────────────────

async def receive_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if msg.photo:
        file_id = msg.photo[-1].file_id
        media_type = "photo"
        caption = msg.caption or ""
    elif msg.video:
        file_id = msg.video.file_id
        media_type = "video"
        caption = msg.caption or ""
    elif msg.document:
        mime = msg.document.mime_type or ""
        if mime.startswith("image/"):
            media_type = "photo"
        elif mime.startswith("video/"):
            media_type = "video"
        else:
            await msg.reply_text("⚠️ 仅支持图片和视频文件。")
            return
        file_id = msg.document.file_id
        caption = msg.caption or ""
    else:
        return

    context.user_data["pending_media"] = {
        "file_id": file_id,
        "media_type": media_type,
        "caption": caption,
    }

    folders = db.get_all_folders()
    if not folders:
        await msg.reply_text(
            "📂 你还没有任何文件夹。\n请先输入一个文件夹名称来创建：",
        )
        context.user_data["after_folder_create"] = "classify"
        return WAITING_FOLDER_NAME

    rows = []
    for f in folders:
        count = db.count_media(f["id"])
        rows.append([InlineKeyboardButton(
            f"📁 {f['name']}  ({count})",
            callback_data=f"classify:{f['id']}"
        )])
    rows.append([InlineKeyboardButton("➕ 新建文件夹", callback_data="new_folder_for_media")])
    kb = InlineKeyboardMarkup(rows)

    icon = "🖼️" if media_type == "photo" else "🎬"
    await msg.reply_text(f"{icon} 收到媒体！请选择要存入的文件夹：", reply_markup=kb)
    return WAITING_CLASSIFY_CHOICE

# ─────────────────────────────────────────────
# Classify media → folder
# ─────────────────────────────────────────────

async def classify_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    folder_id = int(query.data.split(":")[1])
    folder = db.get_folder(folder_id)
    pending = context.user_data.get("pending_media")
    if not pending or not folder:
        await query.edit_message_text("⚠️ 出错了，请重新发送媒体。")
        return ConversationHandler.END

    db.add_media(folder_id, pending["file_id"], pending["media_type"], pending["caption"])
    count = db.count_media(folder_id)
    await query.edit_message_text(
        f"✅ 已保存到 📁 {folder['name']}\n该文件夹共 {count} 个文件。",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("📁 查看文件夹", callback_data=f"view_folder:{folder_id}"),
            InlineKeyboardButton("🏠 主菜单", callback_data="main_menu"),
        ]])
    )
    context.user_data.pop("pending_media", None)
    return ConversationHandler.END

# ─────────────────────────────────────────────
# Folder CRUD callbacks
# ─────────────────────────────────────────────

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    # ── Main menu ──
    if data == "main_menu":
        await send_main_menu(update, context)
        return ConversationHandler.END

    # ── List folders ──
    if data == "list_folders":
        folders = db.get_all_folders()
        if not folders:
            await query.edit_message_text(
                "📂 暂无文件夹，请先创建一个。",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("➕ 新建文件夹", callback_data="create_folder"),
                    InlineKeyboardButton("🔙 返回", callback_data="main_menu"),
                ]])
            )
            return

        rows = []
        for f in folders:
            count = db.count_media(f["id"])
            rows.append([InlineKeyboardButton(
                f"📁 {f['name']}  ({count}个文件)",
                callback_data=f"view_folder:{f['id']}"
            )])
        rows.append([InlineKeyboardButton("🔙 返回主菜单", callback_data="main_menu")])
        await query.edit_message_text("📂 你的所有文件夹：", reply_markup=InlineKeyboardMarkup(rows))
        return

    # ── View folder contents ──
    if data.startswith("view_folder:"):
        folder_id = int(data.split(":")[1])
        await show_folder_contents(query, context, folder_id, page=0)
        return

    # ── Paginate folder ──
    if data.startswith("page:"):
        _, folder_id, page = data.split(":")
        await show_folder_contents(query, context, int(folder_id), int(page))
        return

    # ── Create folder ──
    if data in ("create_folder", "new_folder_for_media"):
        if data == "new_folder_for_media":
            context.user_data["after_folder_create"] = "classify"
        await query.edit_message_text("📝 请输入新文件夹的名称：")
        return WAITING_FOLDER_NAME

    # ── Rename folder ──
    if data == "rename_folder":
        kb = folders_keyboard("rename_pick")
        if not kb:
            await query.edit_message_text("📂 暂无文件夹可重命名。",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 返回", callback_data="main_menu")]]))
            return
        await query.edit_message_text("✏️ 选择要重命名的文件夹：", reply_markup=kb)
        return

    if data.startswith("rename_pick:"):
        folder_id = int(data.split(":")[1])
        context.user_data["rename_folder_id"] = folder_id
        folder = db.get_folder(folder_id)
        await query.edit_message_text(f"✏️ 当前名称：{folder['name']}\n请输入新名称：")
        return WAITING_RENAME_NAME

    # ── Delete folder menu ──
    if data == "delete_folder_menu":
        kb = folders_keyboard("delete_folder_confirm")
        if not kb:
            await query.edit_message_text("📂 暂无文件夹可删除。",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 返回", callback_data="main_menu")]]))
            return
        await query.edit_message_text("🗑️ 选择要删除的文件夹：", reply_markup=kb)
        return

    if data.startswith("delete_folder_confirm:"):
        folder_id = int(data.split(":")[1])
        folder = db.get_folder(folder_id)
        count = db.count_media(folder_id)
        await query.edit_message_text(
            f"⚠️ 确认删除 📁 {folder['name']}？\n该文件夹含 {count} 个文件（仅删除记录，不影响原文件）",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("✅ 确认删除", callback_data=f"delete_folder_do:{folder_id}"),
                    InlineKeyboardButton("❌ 取消", callback_data="main_menu"),
                ]
            ])
        )
        return

    if data.startswith("delete_folder_do:"):
        folder_id = int(data.split(":")[1])
        folder = db.get_folder(folder_id)
        db.delete_folder(folder_id)
        await query.edit_message_text(
            f"✅ 已删除文件夹 📁 {folder['name']}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 主菜单", callback_data="main_menu")]])
        )
        return

    # ── Delete single media — step 1: ask for confirmation ──
    if data.startswith("delete_media:"):
        parts = data.split(":")
        media_id, folder_id, page = int(parts[1]), int(parts[2]), int(parts[3])
        media = db.get_media_by_id(media_id)
        icon = "🖼️" if media and media["media_type"] == "photo" else "🎬"
        label = (media["caption"][:20] if media and media["caption"] else f"#{media_id}")
        await query.edit_message_text(
            f"⚠️ 确认删除这个文件吗？\n{icon} {label}\n\n此操作不可撤销。",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("✅ 确认删除", callback_data=f"confirm_delete_media:{media_id}:{folder_id}:{page}"),
                    InlineKeyboardButton("❌ 取消", callback_data=f"view_folder:{folder_id}"),
                ]
            ])
        )
        return

    # ── Delete single media — step 2: confirmed ──
    if data.startswith("confirm_delete_media:"):
        parts = data.split(":")
        media_id, folder_id, page = int(parts[1]), int(parts[2]), int(parts[3])
        db.delete_media(media_id)
        await show_folder_contents(query, context, folder_id, page)
        return

    # ── Back to folder list from view ──
    if data == "back_to_folders":
        folders = db.get_all_folders()
        rows = [[InlineKeyboardButton(
            f"📁 {f['name']}  ({db.count_media(f['id'])}个文件)",
            callback_data=f"view_folder:{f['id']}"
        )] for f in folders]
        rows.append([InlineKeyboardButton("🔙 返回主菜单", callback_data="main_menu")])
        await query.edit_message_text("📂 你的所有文件夹：", reply_markup=InlineKeyboardMarkup(rows))
        return

async def show_folder_contents(query, context, folder_id: int, page: int = 0):
    PAGE_SIZE = 5
    folder = db.get_folder(folder_id)
    if not folder:
        await query.edit_message_text("⚠️ 文件夹不存在。")
        return

    media_list = db.get_media(folder_id)
    total = len(media_list)

    if total == 0:
        await query.edit_message_text(
            f"📁 {folder['name']}\n\n📭 文件夹为空",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 返回", callback_data="back_to_folders"),
                InlineKeyboardButton("🏠 主菜单", callback_data="main_menu"),
            ]])
        )
        return

    start = page * PAGE_SIZE
    end = min(start + PAGE_SIZE, total)
    page_items = media_list[start:end]

    rows = []
    for m in page_items:
        icon = "🖼️" if m["media_type"] == "photo" else "🎬"
        label = m["caption"][:20] if m["caption"] else f"#{m['id']}"
        rows.append([InlineKeyboardButton(
            f"{icon} {label}",
            callback_data=f"noop"
        ), InlineKeyboardButton(
            "🗑️",
            callback_data=f"delete_media:{m['id']}:{folder_id}:{page}"
        )])

    # Pagination
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀️ 上一页", callback_data=f"page:{folder_id}:{page-1}"))
    if end < total:
        nav.append(InlineKeyboardButton("▶️ 下一页", callback_data=f"page:{folder_id}:{page+1}"))
    if nav:
        rows.append(nav)

    rows.append([
        InlineKeyboardButton("📤 发送全部", callback_data=f"send_all:{folder_id}"),
        InlineKeyboardButton("🔙 返回", callback_data="back_to_folders"),
    ])

    text = (
        f"📁 {folder['name']}\n"
        f"共 {total} 个文件  第 {page+1}/{(total-1)//PAGE_SIZE+1} 页\n"
        f"────────────────\n"
        f"点击 🗑️ 可删除对应文件"
    )
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(rows))

# ─────────────────────────────────────────────
# Send all media in folder
# ─────────────────────────────────────────────

async def send_all_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("正在发送，请稍候…")
    folder_id = int(query.data.split(":")[1])
    folder = db.get_folder(folder_id)
    media_list = db.get_media(folder_id)

    if not media_list:
        await query.answer("文件夹为空！", show_alert=True)
        return

    await context.bot.send_message(
        query.message.chat_id,
        f"📁 正在发送 {folder['name']} 中的 {len(media_list)} 个文件…"
    )
    for m in media_list:
        try:
            caption = m["caption"] or ""
            if m["media_type"] == "photo":
                await context.bot.send_photo(query.message.chat_id, m["file_id"], caption=caption)
            else:
                await context.bot.send_video(query.message.chat_id, m["file_id"], caption=caption)
        except Exception as e:
            logger.warning(f"发送失败 media_id={m['id']}: {e}")
    await context.bot.send_message(query.message.chat_id, "✅ 全部发送完毕！")

# ─────────────────────────────────────────────
# Conversation: create folder
# ─────────────────────────────────────────────

async def receive_folder_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    if not name:
        await update.message.reply_text("⚠️ 文件夹名称不能为空，请重新输入：")
        return WAITING_FOLDER_NAME

    if db.folder_exists(name):
        await update.message.reply_text(f"⚠️ 文件夹「{name}」已存在，请换个名称：")
        return WAITING_FOLDER_NAME

    folder_id = db.create_folder(name)
    after = context.user_data.pop("after_folder_create", None)

    if after == "classify" and context.user_data.get("pending_media"):
        pending = context.user_data["pending_media"]
        db.add_media(folder_id, pending["file_id"], pending["media_type"], pending["caption"])
        context.user_data.pop("pending_media", None)
        await update.message.reply_text(
            f"✅ 文件夹「{name}」已创建，媒体已存入！",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("📁 查看文件夹", callback_data=f"view_folder:{folder_id}"),
                InlineKeyboardButton("🏠 主菜单", callback_data="main_menu"),
            ]])
        )
    else:
        await update.message.reply_text(
            f"✅ 文件夹「{name}」已创建！",
            reply_markup=main_menu_keyboard()
        )
    return ConversationHandler.END

# ─────────────────────────────────────────────
# Conversation: rename folder
# ─────────────────────────────────────────────

async def receive_rename(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_name = update.message.text.strip()
    folder_id = context.user_data.pop("rename_folder_id", None)
    if not folder_id or not new_name:
        await update.message.reply_text("⚠️ 出错了，请重试。")
        return ConversationHandler.END

    if db.folder_exists(new_name):
        await update.message.reply_text(f"⚠️ 名称「{new_name}」已存在，请换个名称：")
        context.user_data["rename_folder_id"] = folder_id
        return WAITING_RENAME_NAME

    db.rename_folder(folder_id, new_name)
    await update.message.reply_text(
        f"✅ 已重命名为「{new_name}」",
        reply_markup=main_menu_keyboard()
    )
    return ConversationHandler.END

# ─────────────────────────────────────────────
# Cancel
# ─────────────────────────────────────────────

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await send_main_menu(update, context, "❌ 已取消操作。")
    return ConversationHandler.END

# ─────────────────────────────────────────────
# noop callback
# ─────────────────────────────────────────────

async def noop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()

# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────

def main():
    token = os.environ.get("BOT_TOKEN")
    if not token:
        raise RuntimeError("请设置环境变量 BOT_TOKEN")

    app = Application.builder().token(token).build()

    conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.PHOTO | filters.VIDEO | filters.Document.ALL, receive_media),
            CallbackQueryHandler(button_handler, pattern="^create_folder$"),
            CallbackQueryHandler(button_handler, pattern="^new_folder_for_media$"),
            CallbackQueryHandler(button_handler, pattern="^rename_pick:"),
        ],
        states={
            WAITING_FOLDER_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_folder_name),
            ],
            WAITING_RENAME_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_rename),
            ],
            WAITING_CLASSIFY_CHOICE: [
                CallbackQueryHandler(classify_media, pattern="^classify:"),
                CallbackQueryHandler(button_handler, pattern="^new_folder_for_media$"),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=False,
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", start))
    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(send_all_media, pattern="^send_all:"))
    app.add_handler(CallbackQueryHandler(noop, pattern="^noop$"))
    app.add_handler(CallbackQueryHandler(button_handler))

    logger.info("Bot 启动中…")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
