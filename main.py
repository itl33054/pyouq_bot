# main.py

import logging
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    filters,
)

from config import (
    TOKEN, 
    CHOOSING, 
    GETTING_POST, 
    BROWSING_POSTS, 
    BROWSING_COLLECTIONS,
    COMMENTING
)
from database import setup_database
from handlers.start_menu import start, back_to_main
from handlers.submission import (
    prompt_submission, 
    handle_new_post, 
    navigate_my_posts, 
    show_my_collections, 
    cancel
)
from handlers.approval import handle_approval, handle_rejection
from handlers.channel_interact import handle_channel_interaction
from handlers.commenting import prompt_comment, handle_new_comment


# --- 全局日志配置 ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
    level=logging.INFO
)
logger = logging.getLogger(__name__)


def main() -> None:
    """
    总装并启动机器人 (V10.2 - 带作者页脚版)。
    """
    application = Application.builder().token(TOKEN).post_init(setup_database).build()

    # --- 主对话处理器 ---
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSING: [
                CallbackQueryHandler(prompt_submission, pattern='^submit_post
    application.add_handler(conv_handler)

    # --- 独立的后台/频道处理器 ---
    application.add_handler(CallbackQueryHandler(handle_approval, pattern='^approve:'))
    application.add_handler(CallbackQueryHandler(handle_rejection, pattern='^decline:'))
    application.add_handler(CallbackQueryHandler(handle_channel_interaction, pattern='^(react|collect|comment)'))
    
    logger.info("🚀 机器人 V10.2 (带作者页脚版) 已启动...")
    
    # 清除待处理的更新，避免冲突
    application.run_polling(drop_pending_updates=True)


if __name__ == '__main__':
    main()
),
                CallbackQueryHandler(navigate_my_posts, pattern='^my_posts_page:'),
                CallbackQueryHandler(show_my_collections, pattern='^my_collections_page:'),
            ],
            GETTING_POST: [
                MessageHandler(filters.ChatType.PRIVATE & ~filters.COMMAND, handle_new_post),
            ],
            BROWSING_POSTS: [
                CallbackQueryHandler(navigate_my_posts, pattern='^my_posts_page:'),
                CallbackQueryHandler(back_to_main, pattern='^back_to_main
    application.add_handler(conv_handler)

    # --- 独立的后台/频道处理器 ---
    application.add_handler(CallbackQueryHandler(handle_approval, pattern='^approve:'))
    application.add_handler(CallbackQueryHandler(handle_rejection, pattern='^decline:'))
    application.add_handler(CallbackQueryHandler(handle_channel_interaction, pattern='^(react|collect|comment)'))
    
    logger.info("🚀 机器人 V10.2 (带作者页脚版) 已启动...")
    
    # 清除待处理的更新，避免冲突
    application.run_polling(drop_pending_updates=True)


if __name__ == '__main__':
    main()
),
            ],
            BROWSING_COLLECTIONS: [
                CallbackQueryHandler(show_my_collections, pattern='^my_collections_page:'),
                CallbackQueryHandler(back_to_main, pattern='^back_to_main
    application.add_handler(conv_handler)

    # --- 独立的后台/频道处理器 ---
    application.add_handler(CallbackQueryHandler(handle_approval, pattern='^approve:'))
    application.add_handler(CallbackQueryHandler(handle_rejection, pattern='^decline:'))
    application.add_handler(CallbackQueryHandler(handle_channel_interaction, pattern='^(react|collect|comment)'))
    
    logger.info("🚀 机器人 V10.2 (带作者页脚版) 已启动...")
    
    # 清除待处理的更新，避免冲突
    application.run_polling(drop_pending_updates=True)


if __name__ == '__main__':
    main()
),
            ],
            COMMENTING: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_new_comment)
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CommandHandler("start", start)
        ],
        allow_reentry=True,
        per_message=True,  # 改为 True 来消除警告
        per_chat=True,
        per_user=True,
    )
    application.add_handler(conv_handler)

    # --- 独立的后台/频道处理器 ---
    application.add_handler(CallbackQueryHandler(handle_approval, pattern='^approve:'))
    application.add_handler(CallbackQueryHandler(handle_rejection, pattern='^decline:'))
    application.add_handler(CallbackQueryHandler(handle_channel_interaction, pattern='^(react|collect|comment)'))
    
    logger.info("🚀 机器人 V10.2 (带作者页脚版) 已启动...")
    
    # 清除待处理的更新，避免冲突
    application.run_polling(drop_pending_updates=True)


if __name__ == '__main__':
    main()
