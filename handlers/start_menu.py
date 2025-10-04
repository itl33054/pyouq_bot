# handlers/start_menu.py

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from config import CHOOSING, COMMENTING
# 导入评论提示函数，以便直接调用
from .commenting import prompt_comment 

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    总入口函数，处理普通 /start 和深度链接 /start。
    """
    # --- V9.3 核心：检查深度链接参数 ---
    if context.args and len(context.args) > 0:
        payload = context.args[0]
        # 检查是否是评论深度链接，格式: "comment_MSGID"
        if payload.startswith("comment_"):
            message_id_str = payload.split("_", 1)[1]
            try:
                message_id = int(message_id_str)
                # 将 message_id 存入 context，以便 prompt_comment 函数可以获取
                context.user_data['deep_link_message_id'] = message_id
                
                # 直接调用/跳转到发表评论的逻辑
                return await prompt_comment(update, context)
            except (IndexError, ValueError):
                # 如果参数格式不对，就忽略它，走下面的标准流程
                pass

    # --- 标准流程：显示主菜单 ---
    keyboard = [
        [
            InlineKeyboardButton("✍️ 发布朋友圈", callback_data='submit_post'),
            InlineKeyboardButton("📒 我的朋友圈", callback_data='my_posts_page:1')
        ],
        [
            InlineKeyboardButton("⭐ 我的收藏", callback_data='my_collections_page:1')
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # 如果是通过按钮返回，则编辑消息；如果是/start命令，则回复新消息
    if update.callback_query:
        await update.callback_query.edit_message_text("你好！请选择一个操作：", reply_markup=reply_markup)
    else:
        await update.message.reply_text("你好！请选择一个操作：", reply_markup=reply_markup)
        
    return CHOOSING

async def back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """处理“返回主菜单”的按钮点击，本质上是重新调用 start 函数的逻辑"""
    if update.callback_query:
        await update.callback_query.answer()
    # 直接调用 start 函数来重绘主菜单
    return await start(update, context)