"""
数据备份与恢复服务

提供组织级别的数据备份、恢复、自动备份调度和过期清理功能。
备份数据以 JSON 格式存储在 backup_records 表中。
"""

import asyncio
import json
import logging
from datetime import UTC, datetime, timedelta

logger = logging.getLogger(__name__)

# 默认备份表
DEFAULT_BACKUP_TABLES = [
    "users",
    "approval_requests",
    "documents",
    "customers",
    "contracts",
]


class BackupService:
    """数据备份与恢复服务"""

    async def create_backup(
        self,
        org_id: str,
        tables: list[str] | None = None,
        created_by: str | None = None,
        backup_type: str = "manual",
        db=None,
    ) -> dict:
        """
        创建组织数据备份

        将指定表的数据导出为 JSON，存储到 backup_records 表。
        默认备份表: users, approval_requests, documents, customers, contracts

        Args:
            org_id: 组织 ID
            tables: 要备份的表名列表（默认使用 DEFAULT_BACKUP_TABLES）
            created_by: 创建人用户 ID
            backup_type: 备份类型 (manual/auto/pre_restore)
            db: 数据库客户端

        Returns:
            备份记录信息
        """
        if not db:
            raise RuntimeError("数据库连接不可用")

        tables_to_backup = tables or DEFAULT_BACKUP_TABLES
        backup_data = {}
        total_size = 0

        try:

            async def _query_table(table_name: str):
                try:
                    result = await db.table(table_name).select("*").eq("organization_id", org_id).execute()
                    return table_name, result.data or [], None
                except Exception as e:
                    return table_name, [], e

            results = await asyncio.gather(*[_query_table(t) for t in tables_to_backup])

            for table_name, table_data, error in results:
                if error:
                    logger.warning(f"备份表 {table_name} 失败: {error}")
                    backup_data[table_name] = {"error": str(error), "rows": []}
                else:
                    backup_data[table_name] = table_data
                total_size += len(json.dumps(backup_data[table_name], default=str).encode("utf-8"))

            # 设置过期时间（默认30天）
            expires_at = (datetime.now(UTC) + timedelta(days=30)).isoformat()

            # 写入备份记录
            record = {
                "organization_id": org_id,
                "backup_type": backup_type,
                "tables_included": tables_to_backup,
                "data": backup_data,
                "size_bytes": total_size,
                "status": "completed",
                "created_by": created_by,
                "expires_at": expires_at,
            }

            result = await db.table("backup_records").insert(record).execute()

            if result.data and len(result.data) > 0:
                backup_record = result.data[0]
                logger.info(
                    f"备份创建成功: org={org_id}, type={backup_type}, "
                    f"tables={len(tables_to_backup)}, size={total_size}B"
                )
                return {
                    "id": backup_record.get("id"),
                    "backup_type": backup_type,
                    "tables_included": tables_to_backup,
                    "size_bytes": total_size,
                    "status": "completed",
                    "created_at": backup_record.get("created_at"),
                    "expires_at": expires_at,
                    "table_row_counts": {t: len(d) if isinstance(d, list) else 0 for t, d in backup_data.items()},
                }

            raise RuntimeError("备份记录写入失败")

        except Exception as e:
            logger.error(f"创建备份失败: {e}")
            raise

    async def list_backups(self, org_id: str, db=None) -> list[dict]:
        """
        列出组织的备份记录

        Args:
            org_id: 组织 ID
            db: 数据库客户端

        Returns:
            备份记录列表（不含具体数据内容，减少传输量）
        """
        if not db:
            raise RuntimeError("数据库连接不可用")

        try:
            result = await (
                db.table("backup_records")
                .select("id, backup_type, tables_included, size_bytes, status, created_by, created_at, expires_at")
                .eq("organization_id", org_id)
                .order("created_at", desc=True)
                .execute()
            )

            return result.data or []

        except Exception as e:
            logger.error(f"列出备份记录失败: {e}")
            raise

    async def get_backup(self, backup_id: str, db=None) -> dict | None:
        """
        获取备份详情

        Args:
            backup_id: 备份 ID
            db: 数据库客户端

        Returns:
            备份详情（含数据统计，不含原始数据）
        """
        if not db:
            raise RuntimeError("数据库连接不可用")

        try:
            result = await db.table("backup_records").select("*").eq("id", backup_id).single().execute()

            if not result.data:
                return None

            record = result.data
            data = record.get("data", {})

            # 返回统计信息，不返回原始数据（避免传输过大）
            return {
                "id": record["id"],
                "organization_id": record.get("organization_id"),
                "backup_type": record.get("backup_type"),
                "tables_included": record.get("tables_included", []),
                "size_bytes": record.get("size_bytes"),
                "status": record.get("status"),
                "created_by": record.get("created_by"),
                "created_at": record.get("created_at"),
                "expires_at": record.get("expires_at"),
                "table_row_counts": {t: len(d) if isinstance(d, list) else 0 for t, d in data.items()},
            }

        except Exception as e:
            logger.error(f"获取备份详情失败: {e}")
            raise

    async def restore_preview(self, backup_id: str, db=None) -> dict:
        """
        恢复预览: 显示将恢复的数据统计，不实际执行

        Args:
            backup_id: 备份 ID
            db: 数据库客户端

        Returns:
            恢复预览信息（每个表的行数、预估影响）
        """
        if not db:
            raise RuntimeError("数据库连接不可用")

        try:
            result = await db.table("backup_records").select("*").eq("id", backup_id).single().execute()

            if not result.data:
                return {"error": "备份记录不存在"}

            record = result.data
            data = record.get("data", {})
            tables = record.get("tables_included", [])

            preview = {
                "backup_id": backup_id,
                "backup_type": record.get("backup_type"),
                "created_at": record.get("created_at"),
                "tables": {},
                "total_rows": 0,
                "warning": "恢复操作将覆盖现有数据，建议先创建当前数据的备份。",
            }

            for table_name in tables:
                table_data = data.get(table_name, [])
                row_count = len(table_data) if isinstance(table_data, list) else 0
                preview["tables"][table_name] = {
                    "rows_to_restore": row_count,
                }
                preview["total_rows"] += row_count

            return preview

        except Exception as e:
            logger.error(f"恢复预览失败: {e}")
            raise

    async def restore_backup(
        self,
        backup_id: str,
        tables: list[str] | None = None,
        db=None,
    ) -> dict:
        """
        恢复数据

        Args:
            backup_id: 备份 ID
            tables: 要恢复的表名列表（默认恢复所有备份表）
            db: 数据库客户端

        Returns:
            恢复结果
        """
        if not db:
            raise RuntimeError("数据库连接不可用")

        try:
            # 获取备份数据
            result = await db.table("backup_records").select("*").eq("id", backup_id).single().execute()

            if not result.data:
                return {"error": "备份记录不存在"}

            record = result.data
            data = record.get("data", {})
            org_id = record.get("organization_id")
            tables_to_restore = tables or record.get("tables_included", [])

            # 先创建恢复前备份
            await self.create_backup(
                org_id=org_id,
                tables=tables_to_restore,
                backup_type="pre_restore",
                db=db,
            )

            restore_results = {}

            for table_name in tables_to_restore:
                table_data = data.get(table_name, [])
                if not isinstance(table_data, list) or len(table_data) == 0:
                    restore_results[table_name] = {"status": "skipped", "reason": "无数据"}
                    continue

                try:
                    # 使用 upsert 恢复数据（保留主键冲突时更新）
                    upsert_result = await db.table(table_name).upsert(table_data).execute()
                    restored_count = len(upsert_result.data) if upsert_result.data else 0
                    restore_results[table_name] = {
                        "status": "restored",
                        "rows": restored_count,
                    }
                except Exception as e:
                    logger.warning(f"恢复表 {table_name} 失败: {e}")
                    restore_results[table_name] = {
                        "status": "failed",
                        "error": str(e),
                    }

            logger.info(f"数据恢复完成: backup={backup_id}, org={org_id}")

            return {
                "backup_id": backup_id,
                "organization_id": org_id,
                "tables_restored": restore_results,
                "restored_at": datetime.now(UTC).isoformat(),
            }

        except Exception as e:
            logger.error(f"恢复数据失败: {e}")
            raise

    async def schedule_auto_backup(
        self, org_id: str, frequency: str = "daily", tables: list[str] | None = None, db=None
    ) -> dict:
        """
        设置自动备份计划

        Args:
            org_id: 组织 ID
            frequency: 备份频率 (daily/weekly/monthly)
            tables: 要备份的表
            db: 数据库客户端

        Returns:
            备份计划信息
        """
        if not db:
            raise RuntimeError("数据库连接不可用")

        tables_list = tables or DEFAULT_BACKUP_TABLES

        # 计算下次备份时间
        now = datetime.now(UTC)
        if frequency == "daily":
            next_backup = now + timedelta(days=1)
        elif frequency == "weekly":
            next_backup = now + timedelta(weeks=1)
        elif frequency == "monthly":
            next_backup = now + timedelta(days=30)
        else:
            next_backup = now + timedelta(days=1)

        try:
            schedule_data = {
                "organization_id": org_id,
                "frequency": frequency,
                "tables": tables_list,
                "is_active": True,
                "next_backup_at": next_backup.isoformat(),
            }

            result = await db.table("backup_schedules").upsert(schedule_data, on_conflict="organization_id").execute()

            if result.data and len(result.data) > 0:
                logger.info(f"自动备份计划已设置: org={org_id}, freq={frequency}")
                return result.data[0]

            raise RuntimeError("备份计划设置失败")

        except Exception as e:
            logger.error(f"设置自动备份计划失败: {e}")
            raise

    async def cleanup_old_backups(self, org_id: str, keep_days: int = 30, db=None) -> int:
        """
        清理过期备份

        Args:
            org_id: 组织 ID
            keep_days: 保留天数
            db: 数据库客户端

        Returns:
            清理的备份数量
        """
        if not db:
            raise RuntimeError("数据库连接不可用")

        cutoff = (datetime.now(UTC) - timedelta(days=keep_days)).isoformat()

        try:
            result = await (
                db.table("backup_records").delete().eq("organization_id", org_id).lt("created_at", cutoff).execute()
            )

            deleted_count = len(result.data) if result.data else 0
            logger.info(f"清理过期备份: org={org_id}, deleted={deleted_count}")
            return deleted_count

        except Exception as e:
            logger.error(f"清理过期备份失败: {e}")
            raise


backup_service = BackupService()
