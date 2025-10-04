# handlers/approval.py

import aiosqlite
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

# Import the necessary configurations from the root config module
from config import CHANNEL_ID, DB_NAME

# Set up a dedicated logger for this module
logger = logging.getLogger(__name__)


async def handle_approval(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles the 'approve' callback query from the review group.
    (V9.5 - Immersive Comments Version)
    """
    query = update.callback_query
    await query.answer()

    # Parse user_id and message_id from the callback data
    action, user_id_str, message_id_str = query.data.split(':')
    user_id = int(user_id_str)
    message_id = int(message_id_str)
    
    try:
        # --- Step 1: Copy the message to the main channel ---
        # This returns a MessageId object which we use to get the new message_id
        sent_message = await context.bot.copy_message(
            chat_id=CHANNEL_ID,
            from_chat_id=user_id,
            message_id=message_id
        )
        msg_id = sent_message.message_id
        
        # --- V9.5 Core Upgrade: The main 'Comment' button is now a functional callback button ---
        # It triggers the 'comment:show' action, handled by channel_interact.py
        keyboard = [[
            InlineKeyboardButton(f"👍 赞 0", callback_data=f"react:like:{msg_id}"),
            InlineKeyboardButton(f"👎 踩 0", callback_data=f"react:dislike:{msg_id}"),
            InlineKeyboardButton("💬 评论 0", callback_data=f"comment:show:{msg_id}"),
            InlineKeyboardButton(f"⭐ 收藏 0", callback_data=f"collect:{msg_id}"),
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # --- Step 2: Attach the interactive keyboard to the newly sent message ---
        await context.bot.edit_message_reply_markup(
            chat_id=CHANNEL_ID,
            message_id=msg_id,
            reply_markup=reply_markup
        )

        # --- Step 3: Save the submission record to the database ---
        admin_message = query.message
        content_to_save = ""
        # Smartly extract text content (from either text or caption)
        if admin_message.text:
            content_to_save = admin_message.text
        elif admin_message.caption:
            # Extract the original caption from the "Submitter Info\n\nOriginal Caption" format
            caption_parts = admin_message.caption.split('\n\n', 1)
            if len(caption_parts) > 1:
                content_to_save = caption_parts[1]

        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute(
                "INSERT INTO submissions (user_id, user_name, channel_message_id, content_text) VALUES (?, ?, ?, ?)",
                (user_id, query.from_user.full_name, msg_id, content_to_save)
            )
            await db.commit()

        # --- Step 4: Update the message in the review group and notify the user ---
        original_caption = query.message.caption or ""
        await query.edit_message_caption(
            caption=f"✅ 已通过 by {query.from_user.first_name}\n\n{original_caption}",
            parse_mode=ParseMode.HTML
        )
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