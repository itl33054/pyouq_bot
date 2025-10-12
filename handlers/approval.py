# handlers/approval.py

import aiosqlite
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

# Import the necessary configurations from the root config module
from config import CHANNEL_ID, DB_NAME, BOT_USERNAME

# Set up a dedicated logger for this module
logger = logging.getLogger(__name__)


async def handle_approval(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles the 'approve' callback query from the review group.
    (V10.2 - 添加作者页脚版)
    """
    query = update.callback_query
    await query.answer()

    # Parse user_id and message_id from the callback data
    action, user_id_str, message_id_str = query.data.split(':')
    user_id = int(user_id_str)
    message_id = int(message_id_str)
    
    try:
        # --- Step 1: Copy the message to the main channel ---
        sent_message = await context.bot.copy_message(
            chat_id=CHANNEL_ID,
            from_chat_id=user_id,
            message_id=message_id
        )
        msg_id = sent_message.message_id
        
        # --- Step 2: 准备内容和页脚 ---
        admin_message = query.message
        content_to_save = ""
        original_caption = ""
        
        # 智能提取文本内容
        if admin_message.text:
            content_to_save = admin_message.text
            original_caption = admin_message.text
        elif admin_message.caption:
            # 从 "投稿人信息\n\n原始文案" 格式中提取原始文案
            caption_parts = admin_message.caption.split('\n\n', 1)
            if len(caption_parts) > 1:
                content_to_save = caption_parts[1]
                original_caption = caption_parts[1]
        
        # --- V10.2 核心：添加作者页脚 ---
        # 获取作者用户名和昵称
        author_username = query.from_user.username or ""
        author_name = query.from_user.full_name or "匿名用户"
        
        # 构建作者链接（如果有用户名）
        if author_username:
            author_link = f'<a href="https://t.me/{author_username}">👤 作者: {author_name}</a>'
        else:
            # 如果没有用户名，使用 tg://user 链接
            author_link = f'<a href="tg://user?id={user_id}">👤 作者: {author_name}</a>'
        
        # 构建"我的"链接
        my_link = f'<a href="https://t.me/{BOT_USERNAME}?start=main">📱 我的</a>'
        
        # 组合完整文案（原内容 + 页脚）
        footer = f"\n\n━━━━━━━━━━━━━━\n{author_link}  |  {my_link}"
        full_caption = (original_caption or "") + footer
        
        # --- Step 3: 先保存到数据库（只保存原始内容，不包含页脚） ---
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute(
                "INSERT INTO submissions (user_id, user_name, channel_message_id, content_text) VALUES (?, ?, ?, ?)",
                (user_id, author_name, msg_id, content_to_save)
            )
            await db.commit()
        
        # --- Step 4: 编辑消息，添加完整的文案和互动按钮 ---
        keyboard = [[
            InlineKeyboardButton(f"👍 赞 0", callback_data=f"react:like:{msg_id}"),
            InlineKeyboardButton(f"👎 踩 0", callback_data=f"react:dislike:{msg_id}"),
            InlineKeyboardButton("💬 评论 0", callback_data=f"comment:show:{msg_id}"),
            InlineKeyboardButton(f"⭐ 收藏 0", callback_data=f"collect:{msg_id}"),
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await context.bot.edit_message_caption(
            chat_id=CHANNEL_ID,
            message_id=msg_id,
            caption=full_caption,
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup
        )

        # --- Step 5: 更新审核群消息 ---
        original_admin_caption = admin_message.caption or ""
        await query.edit_message_caption(
            caption=f"✅ 已通过 by {query.from_user.first_name}\n\n{original_admin_caption}",
            parse_mode=ParseMode.HTML
        )
        
        # --- Step 6: 通知投稿者 ---
        await context.bot.send_message(chat_id=user_id, text="🎉 恭喜！您的投稿已被采纳发布。")
        
    except Exception as e:
        logger.error(f"Failed to process approval: {e}")
        await query.edit_message_caption(caption=f"❌ 发布失败: {e}", parse_mode=ParseMode.HTML)


async def handle_rejection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles the 'decline' callback query from the review group.
    """
    query = update.callback_query
    await query.answer()

    action, user_id_str, message_id_str = query.data.split(':')
    user_id = int(user_id_str)

    # Update the message in the review group to show it was rejected
    original_caption = query.message.caption or ""
    await query.edit_message_caption(
        caption=f"❌ 已拒绝 by {query.from_user.first_name}\n\n{original_caption}",
        parse_mode=ParseMode.HTML
    )
    
    # Notify the original submitter
    await context.bot.send_message(chat_id=user_id, text="很抱歉，您的投稿未通过审核。")
