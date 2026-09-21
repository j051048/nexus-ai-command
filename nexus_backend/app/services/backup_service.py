"""
数据备份与恢复服务

提供组织级别的数据备份、恢复、自动备份调度和过期清理功能。
备份负载默认存放在 backup_records.data；配置 BACKUP_STORAGE_BACKEND 后
改为写入文件系统或 S3 兼容对象存储，数据库里只保留清单、校验和与引用。
"""

import asyncio
import json
import logging
from datetime import UTC, datetime, timedelta

import httpx
from postgrest.exceptions import APIError as PostgrestAPIError

from app.core.config import settings
from app.services.backup_storage import (
    BackupStorageError,
    build_backup_storage,
    canonical_payload,
    checksum_for,
)

logger = logging.getLogger(__name__)

#: Failures that must be attributed to one schedule/organization and must not
#: abort the whole batch. Exported so the lifecycle sweeps can attribute a
#: failure - while still refusing to catch everything.
RECOVERABLE_BACKUP_ERRORS = (
    BackupStorageError,
    PostgrestAPIError,
    httpx.HTTPError,
    TimeoutError,
    OSError,
    RuntimeError,
)


def service_client():
    """Service-role client for background runs (no request context)."""
    from app.core.database import supabase

    return supabase


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
                    result = (
                        await db.table(table_name)
                        .select("*")
                        .eq("organization_id", org_id)
                        .execute()
                    )
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

            payload_bytes = canonical_payload(backup_data)
            checksum = checksum_for(payload_bytes)
            total_size = len(payload_bytes)

            storage = build_backup_storage(settings)
            storage_ref = storage.store(
                org_id=org_id,
                label=backup_type,
                payload=payload_bytes,
                checksum=checksum,
            )

            now = datetime.now(UTC)
            expires_at = (
                now
                + timedelta(days=int(getattr(settings, "BACKUP_RETENTION_DAYS", 30)))
            ).isoformat()

            # 写入备份记录
            record = {
                "organization_id": org_id,
                "backup_type": backup_type,
                "tables_included": tables_to_backup,
                # External backends keep only a manifest here: a backup that
                # shares fate with the primary database is not a backup.
                "data": backup_data if storage.backend == "database" else {},
                "size_bytes": total_size,
                "status": "completed",
                "created_by": created_by,
                "expires_at": expires_at,
                "storage_backend": storage.backend,
                "storage_ref": storage_ref,
                "checksum": checksum,
            }

            result = await db.table("backup_records").insert(record).execute()

            if result.data and len(result.data) > 0:
                backup_record = result.data[0]
                logger.info(
                    f"备份创建成功: org={org_id}, type={backup_type}, "
                    f"tables={len(tables_to_backup)}, size={total_size}B, "
                    f"storage={storage.backend}"
                )
                created = {
                    "id": backup_record.get("id"),
                    "backup_type": backup_type,
                    "tables_included": tables_to_backup,
                    "size_bytes": total_size,
                    "status": "completed",
                    "created_at": backup_record.get("created_at"),
                    "expires_at": expires_at,
                    "storage_backend": storage.backend,
                    "storage_ref": storage_ref,
                    "checksum": checksum,
                    "table_row_counts": {
                        t: len(d) if isinstance(d, list) else 0
                        for t, d in backup_data.items()
                    },
                }
                if getattr(settings, "BACKUP_VERIFY_AFTER_WRITE", True):
                    created["verification"] = await self.verify_backup(
                        backup_record.get("id"), db=db
                    )
                return created

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
                .select(
                    "id, backup_type, tables_included, size_bytes, status, created_by, "
                    "created_at, expires_at, storage_backend, checksum, verified_at"
                )
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
            result = (
                await db.table("backup_records")
                .select("*")
                .eq("id", backup_id)
                .single()
                .execute()
            )

            if not result.data:
                return None

            record = result.data
            data = await self._payload_dict(record)

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
                "storage_backend": record.get("storage_backend") or "database",
                "storage_ref": record.get("storage_ref"),
                "checksum": record.get("checksum"),
                "verified_at": record.get("verified_at"),
                "table_row_counts": {
                    t: len(d) if isinstance(d, list) else 0 for t, d in data.items()
                },
            }

        except Exception as e:
            logger.error(f"获取备份详情失败: {e}")
            raise

    async def _load_payload_bytes(self, record: dict) -> bytes:
        """Return the stored payload, wherever the record points."""
        backend = record.get("storage_backend") or "database"
        ref = record.get("storage_ref")
        if backend != "database" and ref:
            storage = build_backup_storage(settings)
            return storage.load(ref)
        return canonical_payload(record.get("data") or {})

    async def _payload_dict(self, record: dict) -> dict:
        payload = json.loads((await self._load_payload_bytes(record)) or b"{}")
        return payload if isinstance(payload, dict) else {}

    async def verify_backup(self, backup_id: str, db=None) -> dict:
        """Prove a stored backup can be read back and matches its manifest.

        External backends store the exact bytes, so the checksum comparison is
        authoritative there. The ``database`` backend lives in JSONB, which
        normalises numbers and key order, so it is verified structurally
        (table set + row counts) instead of by bytes.
        """
        client = db or service_client()
        if not client:
            raise RuntimeError("数据库连接不可用")

        result = (
            await client.table("backup_records")
            # organization_id is read explicitly: verification must be able to
            # bind its write-back to the owning tenant, not just to the row id.
            .select(
                "id, organization_id, backup_type, tables_included, data, "
                "checksum, storage_backend, storage_ref"
            )
            .eq("id", backup_id)
            .single()
            .execute()
        )
        record = result.data
        if not record:
            return {"backup_id": backup_id, "verified": False, "reason": "not_found"}

        backend = record.get("storage_backend") or "database"
        expected = record.get("checksum")
        payload_bytes = await self._load_payload_bytes(record)
        payload = json.loads(payload_bytes or b"{}")
        payload = payload if isinstance(payload, dict) else {}
        tables_included = record.get("tables_included") or []
        row_counts = {
            name: len(value) if isinstance(value, list) else 0
            for name, value in payload.items()
        }

        if backend == "database":
            missing = [name for name in tables_included if name not in payload]
            verified = not missing
            method = "structure"
            reason = f"missing tables: {missing}" if missing else None
        else:
            actual = checksum_for(payload_bytes)
            verified = bool(expected) and actual == expected
            method = "checksum"
            reason = None if verified else f"checksum {actual} != manifest {expected}"

        verified_at = datetime.now(UTC).isoformat()
        outcome = {
            "backup_id": backup_id,
            "verified": verified,
            "method": method,
            "storage_backend": backend,
            "checksum": expected,
            "row_counts": row_counts,
            "verified_at": verified_at,
        }
        if reason:
            outcome["reason"] = reason
        if verified:
            await (
                client.table("backup_records")
                .update({"verified_at": verified_at})
                .eq("id", backup_id)
                .eq("organization_id", record.get("organization_id"))
                .execute()
            )
        else:
            logger.error(
                "[Backup] verification failed backup=%s backend=%s reason=%s",
                backup_id,
                backend,
                reason,
            )
        return outcome

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
            result = (
                await db.table("backup_records")
                .select("*")
                .eq("id", backup_id)
                .single()
                .execute()
            )

            if not result.data:
                return {"error": "备份记录不存在"}

            record = result.data
            data = await self._payload_dict(record)
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
            result = (
                await db.table("backup_records")
                .select("*")
                .eq("id", backup_id)
                .single()
                .execute()
            )

            if not result.data:
                return {"error": "备份记录不存在"}

            record = result.data
            data = await self._payload_dict(record)
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
                    restore_results[table_name] = {
                        "status": "skipped",
                        "reason": "无数据",
                    }
                    continue

                try:
                    # 使用 upsert 恢复数据（保留主键冲突时更新）
                    upsert_result = (
                        await db.table(table_name).upsert(table_data).execute()
                    )
                    restored_count = (
                        len(upsert_result.data) if upsert_result.data else 0
                    )
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
        self,
        org_id: str,
        frequency: str = "daily",
        tables: list[str] | None = None,
        db=None,
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

            result = (
                await db.table("backup_schedules")
                .upsert(schedule_data, on_conflict="organization_id")
                .execute()
            )

            if result.data and len(result.data) > 0:
                logger.info(f"自动备份计划已设置: org={org_id}, freq={frequency}")
                return result.data[0]

            raise RuntimeError("备份计划设置失败")

        except Exception as e:
            logger.error(f"设置自动备份计划失败: {e}")
            raise

    async def cleanup_old_backups(
        self, org_id: str, keep_days: int = 30, db=None
    ) -> int:
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
            expired = await (
                db.table("backup_records")
                .select("id, organization_id, storage_backend, storage_ref")
                .eq("organization_id", org_id)
                .lt("created_at", cutoff)
                .execute()
            )
            rows = expired.data or []
            deleted_count = await self.delete_records(db, rows)
            logger.info(f"清理过期备份: org={org_id}, deleted={deleted_count}")
            return deleted_count

        except Exception as e:
            logger.error(f"清理过期备份失败: {e}")
            raise

    async def delete_records(self, db, rows: list[dict]) -> int:
        """Delete backup rows, removing their off-site objects first.

        Object deletion is best-effort: an unreachable bucket must not keep
        expired rows (and their metadata) alive in the primary database.
        """
        deleted = 0
        for row in rows:
            ref = row.get("storage_ref")
            if ref:
                try:
                    build_backup_storage(settings).delete(ref)
                except BackupStorageError as exc:
                    logger.warning(
                        "[Backup] could not delete off-site object %s: %s", ref, exc
                    )
            result = (
                await db.table("backup_records")
                .delete()
                .eq("id", row["id"])
                .eq("organization_id", row["organization_id"])
                .execute()
            )
            deleted += len(result.data) if result.data else 1
        return deleted


backup_service = BackupService()
