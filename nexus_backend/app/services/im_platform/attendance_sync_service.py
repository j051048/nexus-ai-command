"""
考勤数据同步服务

从 IM 平台同步考勤打卡数据到 Nexus attendance_records 表。
支持：
- 按组织 + 平台同步
- 将不同平台的考勤数据标准化为统一格式
- 日期默认同步当天
"""

import logging
from datetime import UTC, date, datetime
from typing import Any

from app.core.database import supabase
from app.services.im_platform.contact_sync_service import ContactSyncService

logger = logging.getLogger(__name__)


class AttendanceSyncService:
    """
    考勤数据同步服务。

    从 IM 平台拉取考勤打卡数据，标准化后存入 attendance_records 表。
    """

    def __init__(self):
        self._contact_sync = ContactSyncService()

    async def sync_attendance(
        self,
        org_id: str,
        platform: str,
        sync_date: str = None,
        db=None,
    ) -> dict[str, Any]:
        """
        同步考勤数据。

        Args:
            org_id: 组织 ID
            platform: 平台标识 (wecom/dingtalk/feishu)
            sync_date: 同步日期 YYYY-MM-DD（默认今天）
            db: 数据库客户端

        Returns:
            同步统计:
            {
                "date": "2026-02-14",
                "records_synced": 50,
                "records_created": 10,
                "records_updated": 40,
                "errors": []
            }
        """
        db = db or supabase
        target_date = sync_date or date.today().isoformat()

        stats = {
            "date": target_date,
            "records_synced": 0,
            "records_created": 0,
            "records_updated": 0,
            "errors": [],
        }

        client = None
        try:
            # 1. 获取平台客户端
            client = await self._contact_sync._get_client(org_id, platform, db)
            if not client:
                stats["errors"].append(f"Failed to create {platform} client for org {org_id}")
                return stats

            # 2. 获取该组织在该平台上的所有映射用户
            user_mappings = await self._get_user_mappings(org_id, platform, db)
            if not user_mappings:
                logger.info(f"[AttendanceSync] No user mappings found for org={org_id}, platform={platform}")
                return stats

            # 3. 拉取考勤数据
            platform_user_ids = [m["platform_user_id"] for m in user_mappings]
            raw_records = await client.get_attendance_records(
                user_ids=platform_user_ids,
                start_date=target_date,
                end_date=target_date,
            )

            logger.info(
                f"[AttendanceSync] Fetched {len(raw_records)} raw records from {platform} for date={target_date}"
            )

            # 4. 标准化并存储
            normalized = await self._normalize_attendance(platform, raw_records)

            # 建立 platform_user_id -> nexus_user_id 映射
            user_id_map = {m["platform_user_id"]: m["user_id"] for m in user_mappings}

            for record in normalized:
                platform_user_id = record.get("userid", "")
                nexus_user_id = user_id_map.get(platform_user_id)

                if not nexus_user_id:
                    continue

                try:
                    attendance_data = {
                        "user_id": nexus_user_id,
                        "organization_id": org_id,
                        "platform": platform,
                        "check_date": target_date,
                        "check_in_time": record.get("check_in_time"),
                        "check_out_time": record.get("check_out_time"),
                        "status": record.get("status", "normal"),
                        "location": record.get("location", ""),
                        "raw_data": record.get("raw"),
                        "synced_at": datetime.now(UTC).isoformat(),
                    }

                    # Upsert by unique constraint
                    result = (
                        await db.table("attendance_records")
                        .upsert(
                            attendance_data,
                            on_conflict="user_id,organization_id,platform,check_date",
                        )
                        .execute()
                    )

                    stats["records_synced"] += 1
                    if result.data:
                        # 简化判断: upsert 成功即计为同步
                        stats["records_updated"] += 1

                except Exception as e:
                    logger.warning(f"[AttendanceSync] Failed to upsert attendance for user {platform_user_id}: {e}")
                    stats["errors"].append(f"User {platform_user_id}: {str(e)[:100]}")

            logger.info(
                f"[AttendanceSync] Sync complete for org={org_id}, date={target_date}: synced={stats['records_synced']}"
            )

        except Exception as e:
            error_msg = f"Attendance sync error for org={org_id}: {e}"
            logger.error(f"[AttendanceSync] {error_msg}")
            stats["errors"].append(error_msg)
        finally:
            if client:
                await client.close()

        return stats

    async def _get_user_mappings(self, org_id: str, platform: str, db) -> list[dict]:
        """
        获取组织在指定平台上的所有用户映射。

        Returns:
            [{"user_id": "nexus-uuid", "platform_user_id": "xxx"}, ...]
        """
        try:
            result = (
                await db.table("im_user_mappings")
                .select("user_id, platform_user_id")
                .eq("organization_id", org_id)
                .eq("platform", platform)
                .execute()
            )
            return result.data or []
        except Exception as e:
            logger.error(f"[AttendanceSync] Failed to get user mappings: {e}")
            return []

    async def _normalize_attendance(self, platform: str, raw_records: list[dict]) -> list[dict]:
        """
        将不同平台的考勤数据标准化为统一格式。

        统一格式:
        {
            "userid": "平台用户ID",
            "check_in_time": "ISO datetime or None",
            "check_out_time": "ISO datetime or None",
            "status": "normal|late|early_leave|absent|overtime",
            "location": "打卡地点",
            "raw": {...}  # 原始数据
        }
        """
        normalized = []

        # 按用户分组打卡记录（一天可能有多条记录: 上班/下班）
        user_records: dict[str, list[dict]] = {}
        for record in raw_records:
            uid = record.get("userid", "")
            if uid not in user_records:
                user_records[uid] = []
            user_records[uid].append(record)

        for uid, records in user_records.items():
            entry = {
                "userid": uid,
                "check_in_time": None,
                "check_out_time": None,
                "status": "normal",
                "location": "",
                "raw": records,
            }

            if platform == "wecom":
                entry = self._normalize_wecom(uid, records, entry)
            elif platform == "dingtalk":
                entry = self._normalize_dingtalk(uid, records, entry)
            elif platform == "feishu":
                entry = self._normalize_feishu(uid, records, entry)

            normalized.append(entry)

        return normalized

    @staticmethod
    def _normalize_wecom(uid: str, records: list[dict], entry: dict) -> dict:
        """企微考勤数据标准化"""
        for record in records:
            checkin_type = record.get("checkin_type", "")
            checkin_time = record.get("checkin_time", 0)
            exception_type = record.get("exception_type", "")

            time_str = datetime.fromtimestamp(checkin_time, tz=UTC).isoformat() if checkin_time else None

            # 企微: checkin_type 区分上班/下班
            if "上班" in checkin_type or checkin_type == "":
                entry["check_in_time"] = entry["check_in_time"] or time_str
            elif "下班" in checkin_type:
                entry["check_out_time"] = time_str

            entry["location"] = record.get("location_title", "")

            # 异常类型映射
            if exception_type:
                if "迟到" in exception_type:
                    entry["status"] = "late"
                elif "早退" in exception_type:
                    entry["status"] = "early_leave"
                elif "旷工" in exception_type or "缺卡" in exception_type:
                    entry["status"] = "absent"

        return entry

    @staticmethod
    def _normalize_dingtalk(uid: str, records: list[dict], entry: dict) -> dict:
        """钉钉考勤数据标准化"""
        for record in records:
            check_type = record.get("checkin_type", "")
            checkin_time = record.get("checkin_time", 0)
            time_result = record.get("time_result", "")

            if checkin_time:
                if isinstance(checkin_time, int | float):
                    time_str = datetime.fromtimestamp(checkin_time / 1000, tz=UTC).isoformat()
                else:
                    time_str = str(checkin_time)
            else:
                time_str = None

            if check_type in ("OnDuty", "上班"):
                entry["check_in_time"] = entry["check_in_time"] or time_str
            elif check_type in ("OffDuty", "下班"):
                entry["check_out_time"] = time_str

            # 钉钉 timeResult 状态映射
            if time_result == "Late":
                entry["status"] = "late"
            elif time_result == "Early":
                entry["status"] = "early_leave"
            elif time_result == "Absenteeism":
                entry["status"] = "absent"
            elif time_result == "SeriousLate":
                entry["status"] = "late"

        return entry

    @staticmethod
    def _normalize_feishu(uid: str, records: list[dict], entry: dict) -> dict:
        """飞书考勤数据标准化"""
        for record in records:
            check_type = record.get("checkin_type", "")
            checkin_time = record.get("checkin_time", "")
            check_result = record.get("check_result", "")

            time_str = str(checkin_time) if checkin_time else None

            if check_type in ("PunchIn", "on"):
                entry["check_in_time"] = entry["check_in_time"] or time_str
            elif check_type in ("PunchOut", "off"):
                entry["check_out_time"] = time_str

            entry["location"] = record.get("location_name", "")

            # 飞书 check_result 状态映射
            if check_result == "Late":
                entry["status"] = "late"
            elif check_result == "Early":
                entry["status"] = "early_leave"
            elif check_result == "Lack":
                entry["status"] = "absent"

        return entry


# 模块级单例
attendance_sync_service = AttendanceSyncService()
