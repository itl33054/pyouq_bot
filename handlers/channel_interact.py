# handlers/channel_interact.py

import aiosqlite
import logging
from typing import Tuple, Dict
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ContextTypes
from telegram.error import TelegramError

from config import DB_NAME, BOT_USERNAME, CHANNEL_USERNAME, CHANNEL_ID

logger = logging.getLogger(__name__)


async def check_and_pin_if_hot(context: ContextTypes.DEFAULT_TYPE, message_id: int, like_count: int):
    """检查点赞数，如果达到100自动置顶 (V10.4)"""
    if like_count < 100:
        return
    
    async with aiosqlite.connect(DB_NAME) as db:
        # 检查是否已经记录过置顶
        cursor = await db.execute(
            "SELECT id FROM pinned_posts WHERE channel_message_id = ?",
            (message_id,)
        )
        already_pinned = await cursor.fetchone()
        
        if already_pinned:
            return  # 已经置顶过了
        
        try:
            # 置顶消息
            await context.bot.pin_chat_message(
                chat_id=CHANNEL_ID,
                message_id=message_id,
                disable_notification=True
            )
            
            # 记录到数据库
            await db.execute(
                "INSERT INTO pinned_posts (channel_message_id, like_count_at_pin) VALUES (?, ?)",
                (message_id, like_count)
            )
            await db.commit()
            
            logger.info(f"🔥 帖子 {message_id} 达到 {like_count} 赞，已自动置顶！")
            
            # 通知作者
            cursor = await db.execute(
                "SELECT user_id, content_text FROM submissions WHERE channel_message_id = ?",
                (message_id,)
            )
            post_info = await cursor.fetchone()
            
            if post_info:
                author_id, content_text = post_info
                post_url = f"https://t.me/{CHANNEL_USERNAME}/{message_id}"
                
                preview_text = (content_text or "你的作品")[:30]
                preview_text = preview_text.replace('<', '&lt;').replace('>', '&gt;')
                if len(content_text or "") > 30:
                    preview_text += "..."
                
                notification = (
                    f"🔥 <b>恭喜！你的作品火了！</b>\n\n"
                    f"你的作品 <a href='{post_url}'>{preview_text}</a> 获得了 <b>{like_count}</b> 个赞！\n\n"
                    f"✨ 已被自动置顶到频道顶部，更多人会看到你的精彩内容！"
                )
                
                try:
                    await context.bot.send_message(
                        chat_id=author_id,
                        text=notification,
                        parse_mode=ParseMode.HTML
                    )
                except TelegramError as e:
                    logger.warning(f"发送置顶通知失败: {e}")
                    
        except TelegramError as e:
            logger.error(f"置顶消息失败: {e}")


async def get_all_counts(db, message_id: int) -> Dict[str, int]:
    """查询并返回一个帖子的所有计数"""
    cursor = await db.execute("SELECT reaction_type, COUNT(*) FROM reactions WHERE channel_message_id = ? GROUP BY reaction_type", (message_id,))
    counts = dict(await cursor.fetchall())
    like_count = counts.get(1, 0)
    dislike_count = counts.get(-1, 0)
    
    cursor = await db.execute("SELECT COUNT(*) FROM collections WHERE channel_message_id = ?", (message_id,))
    collection_count = (await cursor.fetchone() or [0])[0]
    
    cursor = await db.execute("SELECT COUNT(*) FROM comments WHERE channel_message_id = ?", (message_id,))
    comment_count = (await cursor.fetchone() or [0])[0]
    
    return {
        "likes": like_count,
        "dislikes": dislike_count,
        "comments": comment_count,
        "collections": collection_count,
    }


async def build_comment_section(db, message_id: int) -> Tuple[str, int]:
    """从数据库构建评论区文本"""
    cursor = await db.execute(
        "SELECT user_id, user_name, comment_text FROM comments WHERE channel_message_id = ? ORDER BY timestamp ASC LIMIT 5",
        (message_id,)
    )
    comments = await cursor.fetchall()
    
    cursor = await db.execute("SELECT COUNT(*) FROM comments WHERE channel_message_id = ?", (message_id,))
    total_comments = (await cursor.fetchone() or [0])[0]

    if not comments:
        return ("\n\n--- 评论区 ---\n✨ 暂无评论，快来抢沙发吧！", 0)
    
    comment_text = f"\n\n--- 评论区 ({total_comments}条) ---\n"
    
    for idx, (uid, uname, text) in enumerate(comments, 1):
        safe_user_name = uname.replace('<', '&lt;').replace('>', '&gt;')
        safe_text = text.replace('<', '&lt;').replace('>', '&gt;')
        comment_text += f'{idx}. <a href="tg://user?id={uid}">{safe_user_name}</a>: {safe_text}\n'
    
    if total_comments > 5:
        comment_text += "...\n"
        
    return (comment_text, total_comments)


async def send_notification(context: ContextTypes.DEFAULT_TYPE, author_id: int, actor_id: int, actor_name: str, 
                            message_id: int, content_preview: str, action_type: str):
    """发送互动通知给作者"""
    # 不要给自己发通知
    if author_id == actor_id:
        return
    
    # 生成作品链接
    post_url = f"https://t.me/{CHANNEL_USERNAME}/{message_id}"
    
    # 生成行为者链接
    actor_link = f'<a href="tg://user?id={actor_id}">{actor_name}</a>'
    
    # 生成作品预览链接
    preview_text = content_preview[:30] + "..." if len(content_preview) > 30 else content_preview
    preview_text = preview_text.replace('<', '&lt;').replace('>', '&gt;')
    post_link = f'<a href="{post_url}">{preview_text}</a>'
    
    # 根据不同的动作类型生成消息
    if action_type == "like":
        message = f"👍 {actor_link} 赞了你的作品 {post_link}"
    elif action_type == "collect":
        message = f"⭐ {actor_link} 收藏了你的作品 {post_link}"
    elif action_type == "comment":
        message = f"💬 {actor_link} 评论了你的作品 {post_link}"
    else:
        return
    
    try:
        await context.bot.send_message(
            chat_id=author_id,
            text=message,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=False
        )
        logger.info(f"通知已发送：{action_type} by {actor_id} to author {author_id}")
    except TelegramError as e:
        logger.warning(f"发送通知失败: {e}")


async def handle_channel_interaction(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """处理频道内的所有按钮点击 (V10.4)"""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user_name = query.from_user.full_name
    message_id = query.message.message_id
    
    callback_data = query.data.split(':')
    action = callback_data[0]

    async with aiosqlite.connect(DB_NAME) as db:
        # 获取原始内容和作者信息
        cursor = await db.execute(
            "SELECT content_text, user_id, user_name FROM submissions WHERE channel_message_id = ?",
            (message_id,)
        )
        db_row = await cursor.fetchone()
        
        if db_row:
            content_text, author_id, author_name = db_row
            
            # 重建页脚
            try:
                author_chat = await context.bot.get_chat(author_id)
                author_username = author_chat.username or ""
            except:
                author_username = ""
            
            if author_username:
                author_link = f'👤 作者: <a href="https://t.me/{author_username}">{author_name}</a>'
            else:
                author_link = f'👤 作者: <a href="tg://user?id={author_id}">{author_name}</a>'
            
            my_link = f'<a href="https://t.me/{BOT_USERNAME}?start=main">📱 我的</a>'
            footer = f"\n\n━━━━━━━━━━━━━━\n{author_link}  |  {my_link}"
            
            base_caption = (content_text or "") + footer
        else:
            current_caption = query.message.caption_html or ""
            base_caption = current_caption.split("\n\n--- 评论区 ---")[0]
            author_id = None
            content_text = ""

        # 动作分支 1: 展开/刷新评论区
        if action == 'comment' and callback_data[1] in ['show', 'refresh']:
            comment_section, _ = await build_comment_section(db, message_id)
            new_caption = base_caption + comment_section
            
            # 构建按钮
            add_comment_link = f"https://t.me/{BOT_USERNAME}?start=comment_{message_id}"
            manage_comment_link = f"https://t.me/{BOT_USERNAME}?start=manage_comments_{message_id}"
            
            comment_keyboard = [
                [
                    InlineKeyboardButton("✍️ 发表评论", url=add_comment_link),
                    InlineKeyboardButton("🗑️ 删除评论", url=manage_comment_link),
                    InlineKeyboardButton("🔄 刷新", callback_data=f"comment:refresh:{message_id}"),
                ],
                [
                    InlineKeyboardButton("⬆️ 收起", callback_data=f"comment:hide:{message_id}"),
                ]
            ]
            
            reply_markup = InlineKeyboardMarkup(comment_keyboard)
            
            if new_caption != query.message.caption_html or reply_markup != query.message.reply_markup:
                try:
                    await query.edit_message_caption(
                        caption=new_caption,
                        parse_mode=ParseMode.HTML,
                        reply_markup=reply_markup
                    )
                except Exception as e:
                    logger.warning(f"展开/刷新评论区失败: {e}")
            return

        # 动作分支 2: 处理点赞、收藏、或收起评论
        notification_type = None
        should_check_pin = False
        
        if action == 'react':
            reaction_type = callback_data[1]
            reaction_value = 1 if reaction_type == 'like' else -1
            
            cursor = await db.execute("SELECT reaction_type FROM reactions WHERE channel_message_id = ? AND user_id = ?", (message_id, user_id))
            existing_reaction = await cursor.fetchone()
            
            if existing_reaction is None:
                # 新增点赞/踩
                await db.execute("INSERT INTO reactions (channel_message_id, user_id, reaction_type) VALUES (?, ?, ?)", (message_id, user_id, reaction_value))
                if reaction_type == 'like':
                    notification_type = "like"
                    should_check_pin = True
            elif existing_reaction[0] == reaction_value:
                # 取消点赞/踩 - 不发通知
                await db.execute("DELETE FROM reactions WHERE channel_message_id = ? AND user_id = ?", (message_id, user_id))
            else:
                # 从踩切换到赞，或从赞切换到踩
                await db.execute("UPDATE reactions SET reaction_type = ? WHERE channel_message_id = ? AND user_id = ?", (reaction_value, message_id, user_id))
                if reaction_type == 'like':
                    notification_type = "like"
                    should_check_pin = True
        
        elif action == 'collect':
            cursor = await db.execute("SELECT id FROM collections WHERE channel_message_id = ? AND user_id = ?", (message_id, user_id))
            is_collected = await cursor.fetchone()
            
            if is_collected:
                await db.execute("DELETE FROM collections WHERE id = ?", (is_collected[0],))
            else:
                await db.execute("INSERT INTO collections (channel_message_id, user_id) VALUES (?, ?)", (message_id, user_id))
                notification_type = "collect"
        
        await db.commit()

        # 发送通知
        if notification_type and author_id:
            await send_notification(
                context, author_id, user_id, user_name, 
                message_id, content_text, notification_type
            )

        # 重新计算所有计数
        counts = await get_all_counts(db, message_id)

        # 检查是否需要置顶
        if should_check_pin and counts['likes'] >= 100:
            await check_and_pin_if_hot(context, message_id, counts['likes'])
            
            # 如果达到100赞，在内容前添加火标识
            if not base_caption.startswith("🔥"):
                base_caption = "🔥 " + base_caption

        # 重绘主按钮栏
        new_main_keyboard = [
            [
                InlineKeyboardButton(f"👍 赞 {counts['likes']}", callback_data=f"react:like:{message_id}"),
                InlineKeyboardButton(f"👎 踩 {counts['dislikes']}", callback_data=f"react:dislike:{message_id}"),
                InlineKeyboardButton(f"⭐ 收藏 {counts['collections']}", callback_data=f"collect:{message_id}"),
            ],
            [
                InlineKeyboardButton(f"💬 评论 {counts['comments']}", callback_data=f"comment:show:{message_id}"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(new_main_keyboard)

        if base_caption != query.message.caption_html or reply_markup != query.message.reply_markup:
            try:
                await query.edit_message_caption(
                    caption=base_caption,
                    parse_mode=ParseMode.HTML,
                    reply_markup=reply_markup
                )
            except Exception as e:
                logger.warning(f"更新主按钮栏失败: {e}")