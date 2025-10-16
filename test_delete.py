# test_delete.py - 测试删除评论功能

import asyncio
import aiosqlite
from config import DB_NAME

async def test_comment_data(message_id: int, user_id: int):
    """测试评论数据"""
    print(f"\n=== 测试帖子 {message_id} 的评论 ===")
    print(f"用户ID: {user_id}")
    
    async with aiosqlite.connect(DB_NAME) as db:
        # 检查帖子是否存在
        cursor = await db.execute(
            "SELECT user_id FROM submissions WHERE channel_message_id = ?",
            (message_id,)
        )
        post_info = await cursor.fetchone()
        
        if not post_info:
            print("❌ 帖子不存在！")
            return
        
        author_id = post_info[0]
        is_author = (user_id == author_id)
        
        print(f"帖子作者ID: {author_id}")
        print(f"是否是作者: {is_author}")
        
        # 查询用户自己的评论
        cursor = await db.execute(
            "SELECT id, comment_text FROM comments WHERE channel_message_id = ? AND user_id = ? ORDER BY timestamp DESC",
            (message_id, user_id)
        )
        my_comments = await cursor.fetchall()
        
        print(f"\n📝 你的评论（{len(my_comments)}条）:")
        for idx, (cid, text) in enumerate(my_comments, 1):
            print(f"  {idx}. ID={cid}, 内容: {text[:30]}...")
        
        # 如果是作者，查询其他人的评论
        if is_author:
            cursor = await db.execute(
                "SELECT id, user_name, comment_text FROM comments WHERE channel_message_id = ? AND user_id != ? ORDER BY timestamp DESC",
                (message_id, user_id)
            )
            other_comments = await cursor.fetchall()
            
            print(f"\n👥 其他人的评论（{len(other_comments)}条）:")
            start_num = len(my_comments) + 1
            for idx, (cid, uname, text) in enumerate(other_comments, start_num):
                print(f"  {idx}. ID={cid}, {uname}: {text[:30]}...")

# 使用方法：
# python test_delete.py
# 然后输入帖子ID和用户ID

if __name__ == "__main__":
    message_id = int(input("输入帖子ID（channel_message_id）: "))
    user_id = int(input("输入你的用户ID: "))
    
    asyncio.run(test_comment_data(message_id, user_id))