# database.py

import aiosqlite
import logging
from telegram.ext import Application

from config import DB_NAME

logger = logging.getLogger(__name__)

async def setup_database(application: Application) -> None:
    """创建或更新所有数据库表结构 (V10.4)"""
    async with aiosqlite.connect(DB_NAME) as db:
        # 主投稿表
        await db.execute('''
            CREATE TABLE IF NOT EXISTS submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT, 
                user_id INTEGER NOT NULL,
                user_name TEXT, 
                channel_message_id INTEGER NOT NULL UNIQUE,
                content_text TEXT, 
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 互动记录表
        await db.execute('''
            CREATE TABLE IF NOT EXISTS reactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT, 
                channel_message_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL, 
                reaction_type INTEGER NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(channel_message_id, user_id)
            )
        ''')
        
        # 收藏记录表
        await db.execute('''
            CREATE TABLE IF NOT EXISTS collections (
                id INTEGER PRIMARY KEY AUTOINCREMENT, 
                channel_message_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL, 
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(channel_message_id, user_id)
            )
        ''')
        
        # 评论表
        await db.execute('''
            CREATE TABLE IF NOT EXISTS comments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_message_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                user_name TEXT NOT NULL,
                comment_text TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 通知记录表
        await db.execute('''
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_message_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                notification_type TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(channel_message_id, user_id, notification_type)
            )
        ''')
        
        # 置顶记录表
        await db.execute('''
            CREATE TABLE IF NOT EXISTS pinned_posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_message_id INTEGER NOT NULL UNIQUE,
                pinned_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                like_count_at_pin INTEGER
            )
        ''')
        
        await db.commit()
        logger.info("数据库已成功连接并初始化 V10.4 表结构。")