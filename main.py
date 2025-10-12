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


logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
    level=logging.INFO
)
logger = logging.getLogger(__name__)


def main() -> None:
    """
    机器人主程序 (V10.2 - 带作者页脚 + 两行按钮布局)
    """
    application = Application.builder().token(TOKEN).post_init(setup_database).build()

    # 主对话处理器
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSING: [
                CallbackQueryHandler(prompt_submission, pattern='^submit_post$'),
                CallbackQueryHandler(navigate_my_posts, pattern='^my_posts_page:'),
                CallbackQueryHandler(show_my_collections, pattern='^my_collections_page:'),
            ],
            GETTING_POST: [
                MessageHandler(filters.ChatType.PRIVATE & ~filters.COMMAND, handle_new_post),
            ],
            BROWSING_POSTS: [
                CallbackQueryHandler(navigate_my_posts, pattern='^my_posts_page:'),
                CallbackQueryHandler(back_to_main, pattern='^back_to_main$'),
            ],
            BROWSING_COLLECTIONS: [
                CallbackQueryHandler(show_my_collections, pattern='^my_collections_page:'),
                CallbackQueryHandler(back_to_main, pattern='^back_to_main$'),
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
        per_message=True,
        per_chat=True,
        per_user=True,
    )
    application.add_handler(conv_handler)

    # 后台处理器
    application.add_handler(CallbackQueryHandler(handle_approval, pattern='^approve:'))
    application.add_handler(CallbackQueryHandler(handle_rejection, pattern='^decline:'))
    application.add_handler(CallbackQueryHandler(handle_channel_interaction, pattern='^(react|collect|comment)'))
    
    logger.info("🚀 机器人 V10.2 启动成功！")
    logger.info("✨ 新功能：作者页脚 + 两行按钮布局")
    
    application.run_polling(drop_pending_updates=True)


if __name__ == '__main__':
    main()
