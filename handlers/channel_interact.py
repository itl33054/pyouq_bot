# handlers/channel_interact.py

import aiosqlite
import logging
from typing import Tuple, Dict
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

# 从根目录的config模块导入
from config import DB_NAME, BOT_USERNAME

# 为这个模块单独设置日志记录器
logger = logging.getLogger(__name__)


async def get_all_counts(db, message_id: int) -> Dict[str, int]:
    """
    一个辅助函数，用于查询并返回一个帖子的所有计数。
    """
    # 点赞/踩
    cursor = await db.execute("SELECT reaction_type, COUNT(*) FROM reactions WHERE channel_message_id = ? GROUP BY reaction_type", (message_id,))
    counts = dict(await cursor.fetchall())
    like_count = counts.get(1, 0)
    dislike_count = counts.get(-1, 0)
    # 收藏
    cursor = await db.execute("SELECT COUNT(*) FROM collections WHERE channel_message_id = ?", (message_id,))
    collection_count = (await cursor.fetchone() or [0])[0]
    # 评论
    cursor = await db.execute("SELECT COUNT(*) FROM comments WHERE channel_message_id = ?", (message_id,))
    comment_count = (await cursor.fetchone() or [0])[0]
    
    return {
        "likes": like_count,
        "dislikes": dislike_count,
        "comments": comment_count,
        "collections": collection_count,
    }


async def build_comment_section(db, message_id: int) -> Tuple[str, int]:
    """
    一个辅助函数，用于从数据库构建带“用户名超链接”的评论区文本。
    """
    # 查询最近的5条评论
    cursor = await db.execute(
        "SELECT user_id, user_name, comment_text FROM comments WHERE channel_message_id = ? ORDER BY timestamp ASC LIMIT 5",
        (message_id,)
    )
    comments = await cursor.fetchall()
    
    # 查询评论总数
    cursor = await db.execute("SELECT COUNT(*) FROM comments WHERE channel_message_id = ?", (message_id,))
    total_comments = (await cursor.fetchone() or [0])[0]

    if not comments:
        return ("\n\n--- 评论区 ---\n✨ 暂无评论，快来抢沙发吧！", 0)
    
    comment_text = f"\n\n--- 评论区 ({total_comments}条) ---\n"
    for user_id, user_name, text in comments:
        safe_user_name = user_name.replace('<', '&lt;').replace('>', '&gt;')
        safe_text = text.replace('<', '&lt;').replace('>', '&gt;')
        comment_text += f'<a href="tg://user?id={user_id}">{safe_user_name}</a>: {safe_text}\n'
    
    if total_comments > 5:
        comment_text += "...\n"
        
    return (comment_text, total_comments)


async def handle_channel_interaction(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    处理频道内的所有按钮点击 (V10.1 - 消除重复编辑警告版)。
    """
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    message_id = query.message.message_id
    
    callback_data = query.data.split(':')
    action = callback_data[0]

    async with aiosqlite.connect(DB_NAME) as db:
        # --- V10.0 核心：无论做什么，都先从数据库获取“原始标题” ---
        cursor = await db.execute(
            "SELECT content_text FROM submissions WHERE channel_message_id = ?",
            (message_id,)
        )
        db_caption_row = await cursor.fetchone()
        base_caption = (db_caption_row[0] if db_caption_row else (query.message.caption or "")).split("\n\n--- 评论区 ---")[0]

        # --- 动作分支 1: 展开/刷新评论区 ---
        if action == 'comment' and callback_data[1] in ['show', 'refresh']:
            comment_section, _ = await build_comment_section(db, message_id)
            new_caption = base_caption + comment_section
            
            deep_link = f"https://t.me/{BOT_USERNAME}?start=comment_{message_id}"
            
            comment_keyboard = [[
                InlineKeyboardButton("✍️ 发表评论", url=deep_link),
                InlineKeyboardButton("🔄 刷新", callback_data=f"comment:refresh:{message_id}"),
                InlineKeyboardButton("⬆️ 收起", callback_data=f"comment:hide:{message_id}"),
            ]]
            reply_markup = InlineKeyboardMarkup(comment_keyboard)
            
            # --- V10.1 核心优化：在编辑前进行比较 ---
            if new_caption != query.message.caption_html or reply_markup != query.message.reply_markup:
                try:
                    await query.edit_message_caption(
                        caption=new_caption,
                        parse_mode=ParseMode.HTML,
                        reply_markup=reply_markup
                    )
                except Exception as e:
                    logger.warning(f"展开/刷新评论区失败 (可能是API限制): {e}")
            return

        # --- 动作分支 2: 处理点赞、收藏、或收起评论，并重绘主按钮栏 ---
        # 1. 数据库更新
        if action == 'react':
            reaction_type = callback_data[1]
            reaction_value = 1 if reaction_type == 'like' else -1
            cursor = await db.execute("SELECT reaction_type FROM reactions WHERE channel_message_id = ? AND user_id = ?", (message_id, user_id))
            existing_reaction = await cursor.fetchone()
            if existing_reaction is None:
                await db.execute("INSERT INTO reactions (channel_message_id, user_id, reaction_type) VALUES (?, ?, ?)", (message_id, user_id, reaction_value))
            elif existing_reaction[0] == reaction_value:
                await db.execute("DELETE FROM reactions WHERE channel_message_id = ? AND user_id = ?", (message_id, user_id))
            else:
                await db.execute("UPDATE reactions SET reaction_type = ? WHERE channel_message_id = ? AND user_id = ?", (reaction_value, message_id, user_id))
        
        elif action == 'collect':
            cursor = await db.execute("SELECT id FROM collections WHERE channel_message_id = ? AND user_id = ?", (message_id, user_id))
            is_collected = await cursor.fetchone()
            if is_collected:
                await db.execute("DELETE FROM collections WHERE id = ?", (is_collected[0],))
            else:
                await db.execute("INSERT INTO collections (channel_message_id, user_id) VALUES (?, ?)", (message_id, user_id))
        
        await db.commit()

        # 2. 统一重新计算所有计数
        counts = await get_all_counts(db, message_id)

        # 3. 统一重绘主按钮栏
        new_main_keyboard = [[
            InlineKeyboardButton(f"👍 赞 {counts['likes']}", callback_data=f"react:like:{message_id}"),
            InlineKeyboardButton(f"👎 踩 {counts['dislikes']}", callback_data=f"react:dislike:{message_id}"),
            InlineKeyboardButton(f"💬 评论 {counts['comments']}", callback_data=f"comment:show:{message_id}"),
            InlineKeyboardButton(f"⭐ 收藏 {counts['collections']}", callback_data=f"collect:{message_id}"),
        ]]
        reply_markup = InlineKeyboardMarkup(new_main_keyboard)

        # --- V10.1 核心优化：在编辑前进行比较 ---
        if base_caption != query.message.caption_html or reply_markup != query.message.reply_markup:
            try:
                await query.edit_message_caption(
                    caption=base_caption,
                    parse_mode=ParseMode.HTML,
                    reply_markup=reply_markup
                )
            except Exception as e:
                logger.warning(f"更新主按钮栏失败 (可能是API限制): {e}")