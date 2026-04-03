"""
P0-4: 记忆生命周期管理
"""

import logging
from datetime import datetime, timedelta

from app.core.database import supabase

logger = logging.getLogger(__name__)


async def cleanup_old_memories(days: int = 90):
    """清理旧记忆"""
    cutoff = datetime.utcnow() - timedelta(days=days)

    try:
        result = await supabase.table("conversation_memories").delete().lt("created_at", cutoff.isoformat()).execute()

        logger.info(f"Cleaned up memories older than {days} days")
        return result
    except Exception as e:
        logger.error(f"Memory cleanup failed: {e}")


async def compress_old_memories(days: int = 30):
    """压缩 30-90 天的记忆"""
    start = datetime.utcnow() - timedelta(days=90)
    end = datetime.utcnow() - timedelta(days=30)

    try:
        result = (
            await supabase.table("conversation_memories")
            .select("id, content")
            .gte("created_at", start.isoformat())
            .lt("created_at", end.isoformat())
            .eq("compressed", False)
            .limit(100)
            .execute()
        )

        for mem in result.data:
            # 简单压缩：截断到前 200 字符
            compressed = mem["content"][:200] + "..."
            await supabase.table("conversation_memories").update({"content": compressed, "compressed": True}).eq(
                "id", mem["id"]
            ).execute()

        logger.info(f"Compressed {len(result.data)} memories")
    except Exception as e:
        logger.error(f"Memory compression failed: {e}")
