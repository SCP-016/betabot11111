import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    filters, ContextTypes, ConversationHandler
)
from database import Database

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

db = Database()

# ConversationHandler states
WAITING_FOLDER_NAME = 1
WAITING_RENAME_NEW = 2
WAITING_RENAME_SELECT = 3

# ── Helpers ──────────────────────────────────────────────────────────────────

def main_menu_keyboard(user_id: int):
    """Bottom-level main menu buttons."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📁 我的文件夹", callback_data="list_folders")],
        [
            InlineKeyboardButton("➕ 新建文件夹", callback_data="create_folder"),
            InlineKeyboardButton("✏️ 重命名", callback_data="rename_folder"),
        ],
        [InlineKeyboardButton("🗑 删除文件夹", callback_data="delete_folder_menu")],
    ])


def folder_list_keyboard(folders, action_prefix: str, back_cb: str = "main_menu"):
    """Generate a keyboard listing all folders."""
    buttons = [
        [InlineKeyboardButton(f"📁 {f['name']}", callback_data=f"{action_prefix}:{f['id']}")]
        for f in folders
    ]
    buttons.append([InlineKeyboardButton("« 返回", callback_data=back_cb)])
    return InlineKeyboardMarkup(buttons)


async def answer_and_edit(query, text, keyboard=None):
    await query.answer()
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode="HTML")


# ── /start ────────────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    db.ensure_user(user_id)
    await update.message.reply_text(
        "👋 <b>媒体分类机器人</b>\n\n"
        "• 转发/发送图片、视频等媒体，机器人会提示你选择文件夹存入。\n"
        "• 使用下方按钮管理文件夹。",
        reply_markup=main_menu_keyboard(user_id),
        parse_mode="HTML",
    )


# ── Main Menu callback ────────────────────────────────────────────────────────

async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await answer_and_edit(query, "🏠 <b>主菜单</b>", main_menu_keyboard(user_id))


# ── List folders ──────────────────────────────────────────────────────────────

async def list_folders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    folders = db.get_folders(user_id)
    if not folders:
        await answer_and_edit(
            query,
            "📭 还没有文件夹，先新建一个吧！",
            InlineKeyboardMarkup([[InlineKeyboardButton("« 返回", callback_data="main_menu")]]),
        )
        return
    kb = [
        [InlineKeyboardButton(f"📁 {f['name']}  ({f['count']} 个媒体)", callback_data=f"open_folder:{f['id']}")]
        for f in folders
    ]
    kb.append([InlineKeyboardButton("« 返回", callback_data="main_menu")])
    await answer_and_edit(query, "📁 <b>我的文件夹</b>", InlineKeyboardMarkup(kb))


# ── Open folder (view media list) ─────────────────────────────────────────────

async def open_folder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    folder_id = int(query.data.split(":")[1])
    folder = db.get_folder(user_id, folder_id)
    if not folder:
        await query.answer("找不到该文件夹", show_alert=True)
        return
    medias = db.get_medias(folder_id)
    if not medias:
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("« 返回", callback_data="list_folders")]])
        await answer_and_edit(query, f"📁 <b>{folder['name']}</b>\n\n（空文件夹）", kb)
        return

    lines = []
    for i, m in enumerate(medias, 1):
        type_emoji = {"photo": "🖼", "video": "🎬", "document": "📄", "audio": "🎵", "animation": "🎞"}.get(m["media_type"], "📎")
        lines.append(f"{i}. {type_emoji} {m['caption'] or m['media_type']}")

    kb = [
        [InlineKeyboardButton(f"🗑 删除媒体", callback_data=f"delete_media_menu:{folder_id}")]
    ]
    kb.append([InlineKeyboardButton("« 返回", callback_data="list_folders")])
    text = f"📁 <b>{folder['name']}</b>  —  {len(medias)} 个媒体\n\n" + "\n".join(lines)
    await answer_and_edit(query, text, InlineKeyboardMarkup(kb))


# ── Create folder ─────────────────────────────────────────────────────────────

async def create_folder_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "📁 请输入新文件夹名称：\n\n发送 /cancel 取消",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("取消", callback_data="main_menu")]]),
    )
    return WAITING_FOLDER_NAME


async def create_folder_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    name = update.message.text.strip()
    if not name:
        await update.message.reply_text("名称不能为空，请重新输入：")
        return WAITING_FOLDER_NAME
    if db.folder_name_exists(user_id, name):
        await update.message.reply_text(f"已存在名为「{name}」的文件夹，请用其他名称：")
        return WAITING_FOLDER_NAME
    db.create_folder(user_id, name)
    await update.message.reply_text(
        f"✅ 文件夹「{name}」创建成功！",
        reply_markup=main_menu_keyboard(user_id),
    )
    return ConversationHandler.END


# ── Rename folder ─────────────────────────────────────────────────────────────

async def rename_folder_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    folders = db.get_folders(user_id)
    if not folders:
        await query.answer("没有文件夹可重命名", show_alert=True)
        return ConversationHandler.END
    await answer_and_edit(
        query, "✏️ 选择要重命名的文件夹：",
        folder_list_keyboard(folders, "rename_select")
    )
    return WAITING_RENAME_SELECT


async def rename_folder_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    folder_id = int(query.data.split(":")[1])
    context.user_data["rename_folder_id"] = folder_id
    await answer_and_edit(query, "✏️ 请输入新名称：\n\n发送 /cancel 取消")
    return WAITING_RENAME_NEW


async def rename_folder_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    new_name = update.message.text.strip()
    folder_id = context.user_data.get("rename_folder_id")
    if not new_name:
        await update.message.reply_text("名称不能为空，请重新输入：")
        return WAITING_RENAME_NEW
    if db.folder_name_exists(user_id, new_name):
        await update.message.reply_text(f"已存在名为「{new_name}」的文件夹，请用其他名称：")
        return WAITING_RENAME_NEW
    db.rename_folder(user_id, folder_id, new_name)
    await update.message.reply_text(
        f"✅ 已重命名为「{new_name}」",
        reply_markup=main_menu_keyboard(user_id),
    )
    return ConversationHandler.END


# ── Delete folder ─────────────────────────────────────────────────────────────

async def delete_folder_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    folders = db.get_folders(user_id)
    if not folders:
        await query.answer("没有文件夹可删除", show_alert=True)
        return
    await answer_and_edit(
        query, "🗑 选择要删除的文件夹：",
        folder_list_keyboard(folders, "delete_folder_confirm")
    )


async def delete_folder_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    folder_id = int(query.data.split(":")[1])
    folder = db.get_folder(user_id, folder_id)
    if not folder:
        await query.answer("找不到该文件夹", show_alert=True)
        return
    count = db.count_medias(folder_id)
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⚠️ 确认删除", callback_data=f"delete_folder_do:{folder_id}"),
            InlineKeyboardButton("取消", callback_data="delete_folder_menu"),
        ]
    ])
    await answer_and_edit(
        query,
        f"⚠️ <b>确认删除文件夹「{folder['name']}」？</b>\n\n"
        f"该文件夹含 {count} 个媒体，将一并删除，此操作不可撤销。",
        kb,
    )


async def delete_folder_do(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    folder_id = int(query.data.split(":")[1])
    folder = db.get_folder(user_id, folder_id)
    name = folder["name"] if folder else "未知"
    db.delete_folder(user_id, folder_id)
    await answer_and_edit(
        query,
        f"✅ 文件夹「{name}」已删除。",
        main_menu_keyboard(user_id),
    )


# ── Delete media ──────────────────────────────────────────────────────────────

async def delete_media_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    folder_id = int(query.data.split(":")[1])
    folder = db.get_folder(user_id, folder_id)
    medias = db.get_medias(folder_id)
    if not medias:
        await query.answer("文件夹为空", show_alert=True)
        return
    type_emoji = lambda t: {"photo": "🖼", "video": "🎬", "document": "📄", "audio": "🎵", "animation": "🎞"}.get(t, "📎")
    kb = [
        [InlineKeyboardButton(
            f"{type_emoji(m['media_type'])} {m['caption'] or m['media_type']} #{i}",
            callback_data=f"delete_media_confirm:{m['id']}:{folder_id}"
        )]
        for i, m in enumerate(medias, 1)
    ]
    kb.append([InlineKeyboardButton("« 返回", callback_data=f"open_folder:{folder_id}")])
    await answer_and_edit(
        query,
        f"🗑 <b>选择要删除的媒体</b>\n（文件夹：{folder['name']}）",
        InlineKeyboardMarkup(kb),
    )


async def delete_media_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    _, media_id, folder_id = query.data.split(":")
    media_id, folder_id = int(media_id), int(folder_id)
    media = db.get_media(media_id)
    if not media:
        await query.answer("找不到该媒体", show_alert=True)
        return
    type_emoji = {"photo": "🖼", "video": "🎬", "document": "📄", "audio": "🎵", "animation": "🎞"}.get(media["media_type"], "📎")
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⚠️ 确认删除", callback_data=f"delete_media_do:{media_id}:{folder_id}"),
            InlineKeyboardButton("取消", callback_data=f"delete_media_menu:{folder_id}"),
        ]
    ])
    await answer_and_edit(
        query,
        f"⚠️ 确认删除这个媒体？\n\n{type_emoji} {media['caption'] or media['media_type']}",
        kb,
    )


async def delete_media_do(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    _, media_id, folder_id = query.data.split(":")
    media_id, folder_id = int(media_id), int(folder_id)
    db.delete_media(media_id)
    await query.answer("✅ 已删除")
    # Refresh the delete media menu
    await delete_media_menu_refresh(query, folder_id)


async def delete_media_menu_refresh(query, folder_id: int):
    """Re-render the media delete list after deletion."""
    user_id = query.from_user.id
    folder = db.get_folder(user_id, folder_id)
    medias = db.get_medias(folder_id)
    if not medias:
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("« 返回文件夹列表", callback_data="list_folders")]])
        await query.edit_message_text(
            f"📁 <b>{folder['name']}</b>\n\n（已清空）",
            reply_markup=kb,
            parse_mode="HTML",
        )
        return
    type_emoji = lambda t: {"photo": "🖼", "video": "🎬", "document": "📄", "audio": "🎵", "animation": "🎞"}.get(t, "📎")
    kb = [
        [InlineKeyboardButton(
            f"{type_emoji(m['media_type'])} {m['caption'] or m['media_type']} #{i}",
            callback_data=f"delete_media_confirm:{m['id']}:{folder_id}"
        )]
        for i, m in enumerate(medias, 1)
    ]
    kb.append([InlineKeyboardButton("« 返回", callback_data=f"open_folder:{folder_id}")])
    await query.edit_message_text(
        f"🗑 <b>选择要删除的媒体</b>\n（文件夹：{folder['name']}）",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="HTML",
    )


# ── Receive media ─────────────────────────────────────────────────────────────

async def receive_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    db.ensure_user(user_id)
    msg = update.message

    # Identify media type & file_id
    if msg.photo:
        media_type = "photo"
        file_id = msg.photo[-1].file_id
    elif msg.video:
        media_type = "video"
        file_id = msg.video.file_id
    elif msg.document:
        media_type = "document"
        file_id = msg.document.file_id
    elif msg.audio:
        media_type = "audio"
        file_id = msg.audio.file_id
    elif msg.animation:
        media_type = "animation"
        file_id = msg.animation.file_id
    else:
        return  # ignore non-media

    caption = msg.caption or ""
    # Store pending media in user_data
    context.user_data["pending_media"] = {
        "file_id": file_id,
        "media_type": media_type,
        "caption": caption,
    }

    folders = db.get_folders(user_id)
    if not folders:
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ 新建文件夹", callback_data="create_folder")]
        ])
        await msg.reply_text("📭 还没有文件夹，请先新建一个。", reply_markup=kb)
        return

    type_emoji = {"photo": "🖼", "video": "🎬", "document": "📄", "audio": "🎵", "animation": "🎞"}.get(media_type, "📎")
    kb = folder_list_keyboard(folders, "save_to_folder", back_cb="main_menu")
    await msg.reply_text(
        f"收到 {type_emoji} <b>{media_type}</b>，请选择要存入的文件夹：",
        reply_markup=kb,
        parse_mode="HTML",
    )


async def save_to_folder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    folder_id = int(query.data.split(":")[1])
    folder = db.get_folder(user_id, folder_id)
    if not folder:
        await query.answer("找不到该文件夹", show_alert=True)
        return

    pending = context.user_data.get("pending_media")
    if not pending:
        await query.answer("没有待存储的媒体，请重新发送", show_alert=True)
        return

    db.add_media(folder_id, pending["file_id"], pending["media_type"], pending["caption"])
    context.user_data.pop("pending_media", None)

    await query.answer(f"✅ 已存入「{folder['name']}」")
    await query.edit_message_text(
        f"✅ 已存入文件夹「{folder['name']}」",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📁 查看文件夹", callback_data=f"open_folder:{folder_id}")],
            [InlineKeyboardButton("🏠 主菜单", callback_data="main_menu")],
        ]),
        parse_mode="HTML",
    )


# ── /cancel ───────────────────────────────────────────────────────────────────

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await update.message.reply_text("已取消。", reply_markup=main_menu_keyboard(user_id))
    return ConversationHandler.END


# ── /menu (re-show main menu) ─────────────────────────────────────────────────

async def menu_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    db.ensure_user(user_id)
    await update.message.reply_text("🏠 主菜单", reply_markup=main_menu_keyboard(user_id))


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    token = os.environ["BOT_TOKEN"]
    app = Application.builder().token(token).build()

    # ConversationHandler: create folder
    create_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(create_folder_start, pattern="^create_folder$")],
        states={
            WAITING_FOLDER_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, create_folder_receive)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=False,
    )

    # ConversationHandler: rename folder
    rename_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(rename_folder_menu, pattern="^rename_folder$")],
        states={
            WAITING_RENAME_SELECT: [
                CallbackQueryHandler(rename_folder_select, pattern="^rename_select:")
            ],
            WAITING_RENAME_NEW: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, rename_folder_receive)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=False,
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", menu_cmd))
    app.add_handler(create_conv)
    app.add_handler(rename_conv)

    # Callbacks
    app.add_handler(CallbackQueryHandler(main_menu, pattern="^main_menu$"))
    app.add_handler(CallbackQueryHandler(list_folders, pattern="^list_folders$"))
    app.add_handler(CallbackQueryHandler(open_folder, pattern="^open_folder:"))
    app.add_handler(CallbackQueryHandler(delete_folder_menu, pattern="^delete_folder_menu$"))
    app.add_handler(CallbackQueryHandler(delete_folder_confirm, pattern="^delete_folder_confirm:"))
    app.add_handler(CallbackQueryHandler(delete_folder_do, pattern="^delete_folder_do:"))
    app.add_handler(CallbackQueryHandler(delete_media_menu, pattern="^delete_media_menu:"))
    app.add_handler(CallbackQueryHandler(delete_media_confirm, pattern="^delete_media_confirm:"))
    app.add_handler(CallbackQueryHandler(delete_media_do, pattern="^delete_media_do:"))
    app.add_handler(CallbackQueryHandler(save_to_folder, pattern="^save_to_folder:"))

    # Media messages
    media_filter = (
        filters.PHOTO | filters.VIDEO | filters.Document.ALL |
        filters.AUDIO | filters.ANIMATION
    )
    app.add_handler(MessageHandler(media_filter, receive_media))

    # Webhook (Render) or polling (local)
    webhook_url = os.environ.get("WEBHOOK_URL")
    port = int(os.environ.get("PORT", 8443))

    if webhook_url:
        app.run_webhook(
            listen="0.0.0.0",
            port=port,
            webhook_url=webhook_url,
            secret_token=os.environ.get("WEBHOOK_SECRET", ""),
        )
    else:
        app.run_polling()


if __name__ == "__main__":
    main()
