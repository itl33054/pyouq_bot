# handlers/commenting.py

import aiosqlite
import logging
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from config import DB_NAME, COMMENTING, CHANNEL_ID
# 导入 channel_interact 中的函数，以便在评论成功后调用它来刷新评论区
# (这是一个高级功能，暂时简化为通知)

logger = logging.getLogger(__name__)

async def prompt_comment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    提示用户输入评论，由深度链接或按钮点击触发。
    """
    message_id = None
    user_id = update.effective_user.id
    
    # --- V9.3 核心：统一处理入口 ---
    if 'deep_link_message_id' in context.user_data:
        message_id = context.user_data.pop('deep_link_message_id')
    
    if not message_id:
        await context.bot.send_message(chat_id=user_id, text="❌ 错误的评论请求。")
        return ConversationHandler.END

    context.user_data['commenting_on_message_id'] = message_id
    
    await context.bot.send_message(
        chat_id=user_id,
        text="✍️ 您正在发表评论，请输入内容：\n\n(输入 /cancel 可随时取消)"
    )
    return COMMENTING


async def handle_new_comment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    接收用户的评论文本，存入数据库，并通知用户。
    """
    user = update.message.from_user
    comment_text = update.message.text
    
    message_id = context.user_data.get('commenting_on_message_id')

    if not message_id:
        await update.message.reply_text("❌ 操作超时或出现错误，请回到频道重试。")
        return ConversationHandler.END

    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT INTO comments (channel_message_id, user_id, user_name, comment_text) VALUES (?, ?, ?, ?)",
            (message_id, user.id, user.full_name, comment_text)
        )
        await db.commit()

    await update.message.reply_text("✅ 评论成功！\n\n帖子的评论数将在下次有人互动时更新。")

    context.user_data.clear()
    return ConversationHandler.END