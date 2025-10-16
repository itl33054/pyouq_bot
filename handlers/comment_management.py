# handlers/comment_management.py

import aiosqlite
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode

from config import DB_NAME, CHANNEL_USERNAME, DELETING_COMMENT

logger = logging.getLogger(__name__)


async def show_delete_comment_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """显示删除评论菜单"""
    user_id = update.effective_user.id
    
    # 检查是来自消息还是回调
    if update.message:
        message = update.message
    elif update.callback_query:
        message = update.callback_query.message
        user_id = update.callback_query.from_user.id
    else:
        return ConversationHandler.END
    
    if not context.args or not context.args[0].startswith('manage_comments_'):
        await message.reply_text("❌ 无效的请求。")
        return ConversationHandler.END
    
    try:
        message_id = int(context.args[0].replace('manage_comments_', ''))
    except ValueError:
        await message.reply_text("❌ 无效的帖子ID。")
        return ConversationHandler.END
    
    async with aiosqlite.connect(DB_NAME) as db:
        # 检查帖子是否存在
        cursor = await db.execute(
            "SELECT user_id FROM submissions WHERE channel_message_id = ?",
            (message_id,)
        )
        post_info = await cursor.fetchone()
        
        if not post_info:
            await message.reply_text("❌ 帖子不存在。")
            return ConversationHandler.END
        
        author_id = post_info[0]
        is_author = (user_id == author_id)
        
        # 查询用户自己的评论
        cursor = await db.execute(
            "SELECT id, comment_text, timestamp FROM comments WHERE channel_message_id = ? AND user_id = ? ORDER BY timestamp DESC",
            (message_id, user_id)
        )
        my_comments = await cursor.fetchall()
        
        # 如果是作者，查询其他人的评论
        other_comments = []
        if is_author:
            cursor = await db.execute(
                "SELECT id, user_id, user_name, comment_text, timestamp FROM comments WHERE channel_message_id = ? AND user_id != ? ORDER BY timestamp DESC",
                (message_id, user_id)
            )
            other_comments = await cursor.fetchall()
    
    # 保存到 context
    context.user_data['delete_mode'] = {
        'message_id': message_id,
        'my_comments': {str(idx): cid for idx, (cid, _, _) in enumerate(my_comments, 1)},
        'other_comments': {str(idx): cid for idx, (cid, _, _, _, _) in enumerate(other_comments, 1)} if is_author else {},
        'is_author': is_author
    }
    
    # 构建消息文本
    message_text = "🗑️ <b>删除评论</b>\n\n"
    
    # 显示"你的评论"
    if my_comments:
        message_text += "📝 <b>你的评论：</b>\n"
        for idx, (comment_id, text, timestamp) in enumerate(my_comments, 1):
            preview = text[:80] + "..." if len(text) > 80 else text
            preview = preview.replace('<', '&lt;').replace('>', '&gt;')
            message_text += f"\n<b>{idx}.</b> {preview}\n"
    else:
        message_text += "📝 <b>你的评论：</b> 暂无评论\n"
    
    # 显示"其他评论"（仅作者可见）
    if is_author:
        message_text += "\n━━━━━━━━━━━━━━\n\n"
        if other_comments:
            message_text += "👥 <b>其他人的评论：</b>\n"
            # V10.4.1 修复：其他人的评论编号从"你的评论数+1"开始
            start_num = len(my_comments) + 1
            for idx, (comment_id, uid, uname, text, timestamp) in enumerate(other_comments, start_num):
                preview = text[:80] + "..." if len(text) > 80 else text
                preview = preview.replace('<', '&lt;').replace('>', '&gt;')
                message_text += f"\n<b>{idx}.</b> <b>{uname}:</b> {preview}\n"
        else:
            message_text += "👥 <b>其他人的评论：</b> 暂无\n"
    
    # 添加使用说明
    message_text += "\n━━━━━━━━━━━━━━\n\n"
    message_text += "💡 <b>如何删除？</b>\n"
    if my_comments:
        message_text += "• 发送数字删除你的评论（如：<code>1</code>）\n"
    if is_author and other_comments:
        message_text += f"• 发送数字删除其他评论（如：<code>{len(my_comments) + 1}</code>）\n"
    message_text += "• 发送 /cancel 取消操作"
    
    # 添加返回按钮
    post_url = f"https://t.me/{CHANNEL_USERNAME}/{message_id}"
    keyboard = [[InlineKeyboardButton("↩️ 返回帖子", url=post_url)]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        message_text,
        parse_mode=ParseMode.HTML,
        reply_markup=reply_markup
    )
    
    return DELETING_COMMENT


async def handle_delete_comment_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """处理用户输入的评论编号"""
    
    # ===== 强制调试：无论什么状态都先回复 =====
    await update.message.reply_text(f"🔍 DEBUG: 收到消息 '{update.message.text}'")
    # ==========================================
    
    user_id = update.message.from_user.id
    text = update.message.text.strip()
    
    logger.info(f"=== 收到删除评论输入 ===")
    logger.info(f"用户ID: {user_id}")
    logger.info(f"输入内容: '{text}'")
    logger.info(f"user_data: {context.user_data}")
    
    delete_data = context.user_data.get('delete_mode')
    if not delete_data:
        logger.warning("❌ delete_mode 数据不存在！")
        await update.message.reply_text(
            "❌ 会话已过期或你没有通过正确的方式进入删除模式。\n\n"
            "正确步骤：\n"
            "1. 在频道点击 💬 评论\n"
            "2. 点击 🗑️ 删除评论\n"
            "3. 跳转到机器人后发送数字"
        )
        return ConversationHandler.END
    
    message_id = delete_data['message_id']
    my_comments = delete_data['my_comments']
    other_comments = delete_data['other_comments']
    is_author = delete_data['is_author']
    
    # 检查输入是否是数字
    if not text.isdigit():
        logger.warning(f"输入不是数字: {text}")
        await update.message.reply_text("❌ 请发送评论编号（数字）。")
        return DELETING_COMMENT
    
    # 检查编号是否存在
    comment_id = None
    comment_owner = None
    
    input_num = int(text)
    my_comment_count = len(my_comments)
    
    # 如果编号 <= 你的评论数，就是删除你的评论
    if input_num <= my_comment_count and str(input_num) in my_comments:
        comment_id = my_comments[str(input_num)]
        comment_owner = "你的"
    # 如果编号 > 你的评论数，就是删除其他人的评论
    elif is_author and input_num > my_comment_count:
        # 转换编号：比如你有1条评论，输入2，实际是其他评论的第1条
        other_index = input_num - my_comment_count
        if str(other_index) in other_comments:
            comment_id = other_comments[str(other_index)]
            comment_owner = "其他人的"
    
    if not comment_id:
        total_count = len(my_comments) + (len(other_comments) if is_author else 0)
        logger.warning(f"编号 {text} 不存在。我的评论: {my_comments.keys()}, 其他评论: {other_comments.keys()}")
        await update.message.reply_text(
            f"❌ 评论编号 {text} 不存在。\n"
            f"请发送 1-{total_count} 之间的数字。"
        )
        return DELETING_COMMENT
    
    # 删除评论
    async with aiosqlite.connect(DB_NAME) as db:
        # 再次验证权限
        cursor = await db.execute(
            "SELECT c.user_id, c.comment_text, c.user_name, s.user_id FROM comments c JOIN submissions s ON c.channel_message_id = s.channel_message_id WHERE c.id = ?",
            (comment_id,)
        )
        comment_info = await cursor.fetchone()
        
        if not comment_info:
            await update.message.reply_text("❌ 评论不存在或已被删除。")
            return ConversationHandler.END
        
        comment_user_id, comment_text, comment_user_name, post_author_id = comment_info
        
        # 检查权限
        if user_id != comment_user_id and user_id != post_author_id:
            await update.message.reply_text("❌ 你没有权限删除这条评论。")
            return ConversationHandler.END
        
        # 删除评论
        await db.execute("DELETE FROM comments WHERE id = ?", (comment_id,))
        await db.commit()
    
    # 成功提示
    preview = comment_text[:50] + "..." if len(comment_text) > 50 else comment_text
    await update.message.reply_text(
        f"✅ 已删除{comment_owner}评论\n\n"
        f"内容：{preview}\n\n"
        f"继续发送编号可删除更多评论，或发送 /cancel 结束。"
    )
    
    logger.info(f"用户 {user_id} 删除了评论 {comment_id}")
    
    # 重新显示评论列表
    context.args = [f"manage_comments_{message_id}"]
    await show_delete_comment_menu(update, context)
    
    return DELETING_COMMENT