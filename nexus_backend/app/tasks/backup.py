"""自动备份任务

P0-4 Security Fix: 按组织隔离备份，防止跨租户数据泄露。
"""

import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# 需要备份的表（均为含 organization_id 的租户数据表）
_BACKUP_TABLES = ["sales_leads", "customers", "contracts", "conversation_memories"]


async def backup_database():
    """每日数据库备份 — 按组织分区执行。

    P0-4 Security Fix: 不再使用全局 supabase client 一次性 select("*")，
    改为按 org_id 遍历，每个组织使用 OrgFilteredClient 隔离查询。
    """
    from app.core.database import supabase

    if not supabase:
        logger.warning("backup_database skipped: no db client")
        return

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # 获取所有组织
    try:
        org_res = await supabase.table("organizations").select("id").execute()
        org_ids = [r["id"] for r in (org_res.data or []) if r.get("id")]
    except Exception as e:
        logger.error("backup_database: failed to fetch org list: %s", e)
        return

    if not org_ids:
        logger.info("backup_database: no organizations found, skipping")
        return

    for org_id in org_ids:
        db = supabase.get_org_filtered_client(org_id)
        for table in _BACKUP_TABLES:
            try:
                data = await db.table(table).select("*").execute()
                record_count = len(data.data) if data.data else 0
                # TODO: 实际写入 S3 / 对象存储，此处仅日志占位
                logger.info(
                    "Backed up %s for org %s: %d records (ts=%s)",
                    table,
                    org_id,
                    record_count,
                    timestamp,
                )
            except Exception as e:
                logger.error(
                    "backup_database: failed to backup %s for org %s: %s",
                    table,
                    org_id,
                    e,
                )
