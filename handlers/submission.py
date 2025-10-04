# handlers/submission.py

import aiosqlite
from datetime import datetime
import math
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ContextTypes, ConversationHandler

# 从根目录的config模块导入所有需要的配置和状态码
from config import (
    ADMIN_GROUP_ID, 
    GETTING_POST, 
    DB_NAME, 
    CHANNEL_USERNAME, 
    CHOOSING, 
    BROWSING_POSTS, 
    BROWSING_COLLECTIONS
)


# --- 投稿对话流程 ---

async def prompt_submission(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    提示用户发送要投稿的内容，并进入 GETTING_POST 状态。
    """
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "好的，现在请发送您要分享的内容（文字、图片、视频等）。\n\n"
        "随时可以输入 /cancel 取消操作。"
    )
    return GETTING_POST


async def handle_new_post(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    处理用户发送的投稿，转发到审核群，并结束对话。
    """
    message = update.message
    user = message.from_user

    approve_callback_data = f"approve:{user.id}:{message.message_id}"
    decline_callback_data = f"decline:{user.id}:{message.message_id}"
    keyboard = [[
        InlineKeyboardButton("✅ 通过", callback_data=approve_callback_data),
        InlineKeyboardButton("❌ 拒绝", callback_data=decline_callback_data),
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    user_info = f"<b>投稿人:</b> {user.full_name} (@{user.username})\n<b>ID:</b> <code>{user.id}</code>"

    try:
        await context.bot.copy_message(
            chat_id=ADMIN_GROUP_ID,
            from_chat_id=user.id,
            message_id=message.id,
            caption=f"{user_info}\n\n{message.caption or ''}",
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )
        await message.reply_text("✅ 您的投稿已成功提交审核。")
    except Exception as e:
        await message.reply_text(f"❌ 抱歉，提交失败: {e}")

    # 结束整个对话流程
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    取消当前所有操作，并结束对话。
    """
    await update.message.reply_text("操作已取消。")
    return ConversationHandler.END


# --- “我的朋友圈”分页浏览 ---

async def navigate_my_posts(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    从数据库查询“我的朋友圈”(用户自己发布的内容)，并展示带导航链接和分页按钮的记录。
    """
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    target_page = int(query.data.split(':')[1])
    posts_per_page = 10

    async with aiosqlite.connect(DB_NAME) as db:
        # 1. 查询该用户自己发布的作品总数
        cursor = await db.execute(
            "SELECT COUNT(*) FROM submissions WHERE user_id = ?", 
            (user_id,)
        )
        total_posts = (await cursor.fetchone())[0]
        
        if total_posts == 0:
            await query.edit_message_text(
                "您还没有发布过任何内容哦。",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ 返回主菜单", callback_data='back_to_main')]])
            )
            return BROWSING_POSTS

        total_pages = math.ceil(total_posts / posts_per_page)
        
        # 2. 查询当前页的数据
        offset = (target_page - 1) * posts_per_page
        cursor = await db.execute(
            "SELECT content_text, timestamp, channel_message_id FROM submissions WHERE user_id = ? ORDER BY timestamp DESC LIMIT ? OFFSET ?",
            (user_id, posts_per_page, offset)
        )
        posts = await cursor.fetchall()

    # 3. 构建带超链接的文本
    response_text = f"您的朋友圈记录 (第 {target_page}/{total_pages} 页)：\n\n"
    for i, post in enumerate(posts):
        content, timestamp, msg_id = post
        post_text = (content or "[媒体文件]").strip().replace('<', '&lt;').replace('>', '&gt;')
        if len(post_text) > 20: 
            post_text = post_text[:20] + "..."
        
        post_url = f"https://t.me/{CHANNEL_USERNAME}/{msg_id}"
        response_text += f"{offset + i + 1}. <a href='{post_url}'>{post_text}</a>\n"

    # 4. 构建包含“返回”的分页按钮
    nav_buttons = []
    if target_page > 1:
        nav_buttons.append(InlineKeyboardButton("⬅️ 上一页", callback_data=f'my_posts_page:{target_page - 1}'))
    if target_page < total_pages:
        nav_buttons.append(InlineKeyboardButton("下一页 ➡️", callback_data=f'my_posts_page:{target_page + 1}'))
    
    keyboard = [
        nav_buttons,
        [InlineKeyboardButton("⬅️ 返回主菜单", callback_data='back_to_main')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # 5. 编辑消息
    await query.edit_message_text(
        response_text,
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True
    )
    
    return BROWSING_POSTS


# --- “我的收藏”分页浏览 ---

async def show_my_collections(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    从数据库查询“我的收藏”，并展示带导航链接和分页按钮的记录。
    """
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    target_page = int(query.data.split(':')[1])
    posts_per_page = 10

    async with aiosqlite.connect(DB_NAME) as db:
        # 1. 查询该用户的收藏总数
        cursor = await db.execute(
            "SELECT COUNT(*) FROM collections WHERE user_id = ?", 
            (user_id,)
        )
        total_posts = (await cursor.fetchone())[0]

        if total_posts == 0:
            await query.edit_message_text(
                "您还没有任何收藏哦。",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ 返回主菜单", callback_data='back_to_main')]])
            )
            return BROWSING_COLLECTIONS

        total_pages = math.ceil(total_posts / posts_per_page)
        offset = (target_page - 1) * posts_per_page

        # 2. 连表查询，获取收藏帖子的原文案和ID
        cursor = await db.execute(
            """
            SELECT s.content_text, s.timestamp, s.channel_message_id
            FROM collections c JOIN submissions s ON c.channel_message_id = s.channel_message_id
            WHERE c.user_id = ? ORDER BY c.timestamp DESC LIMIT ? OFFSET ?
            """,
            (user_id, posts_per_page, offset)
        )
        posts = await cursor.fetchall()
    
    # 3. 构建带超链接的文本
    response_text = f"您的收藏 (第 {target_page}/{total_pages} 页)：\n\n"
    for i, post in enumerate(posts):
        content, timestamp, msg_id = post
        post_text = (content or "[媒体文件]").strip().replace('<', '&lt;').replace('>', '&gt;')
        if len(post_text) > 20: 
            post_text = post_text[:20] + "..."
        
        post_url = f"https://t.me/{CHANNEL_USERNAME}/{msg_id}"
        response_text += f"{offset + i + 1}. <a href='{post_url}'>{post_text}</a>\n"
    
    # 4. 构建包含“返回”的分页按钮
    nav_buttons = []
    if target_page > 1:
        nav_buttons.append(InlineKeyboardButton("⬅️ 上一页", callback_data=f'my_collections_page:{target_page - 1}'))
    if target_page < total_pages:
        nav_buttons.append(InlineKeyboardButton("下一页 ➡️", callback_data=f'my_collections_page:{target_page + 1}'))
    
    keyboard = [
        nav_buttons,
        [InlineKeyboardButton("⬅️ 返回主菜单", callback_data='back_to_main')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # 5. 编辑消息
    await query.edit_message_text(
        response_text,
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True
    )

    return BROWSING_COLLECTIONS