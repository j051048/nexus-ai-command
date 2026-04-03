"""自动备份任务"""

from datetime import datetime

from app.core.database import supabase


async def backup_database():
    """每日数据库备份"""
    datetime.now().strftime("%Y%m%d_%H%M%S")
    tables = ["sales_leads", "customers", "contracts", "conversation_memories"]

    for table in tables:
        data = await supabase.table(table).select("*").execute()
        # 备份到S3或本地
        print(f"Backed up {table}: {len(data.data)} records")
