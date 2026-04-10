"""
考勤管理服务
提供打卡、排班、请假等功能
"""

import logging
from datetime import UTC, datetime

logger = logging.getLogger(__name__)


class AttendanceService:
    """考勤管理服务"""

    async def clock_in_out(
        self,
        org_id: str,
        employee_id: str,
        clock_type: str,
        location: str | None = None,
        device_info: str | None = None,
        db=None,
    ) -> dict:
        """
        打卡（上班/下班/外勤）

        Args:
            org_id: 组织ID
            employee_id: 员工ID (即 user_id)
            clock_type: 打卡类型 (clock_in/clock_out/field_work)
            location: 打卡位置
            device_info: 设备信息
            db: 数据库客户端

        Returns:
            打卡记录
        """
        if not db:
            raise RuntimeError("数据库连接不可用")

        try:
            now = datetime.now(UTC)
            today = now.date().isoformat()

            # Check if a record already exists for today
            existing = (
                await db.table("attendance_records")
                .select("id, check_in_time, check_out_time")
                .eq("user_id", employee_id)
                .eq("organization_id", org_id)
                .eq("check_date", today)
                .maybe_single()
                .execute()
            )

            if existing and existing.data:
                # Update existing record (clock_out or update)
                update_data = {}
                if clock_type == "clock_out":
                    update_data["check_out_time"] = now.isoformat()
                elif clock_type == "clock_in" and not existing.data.get(
                    "check_in_time"
                ):
                    update_data["check_in_time"] = now.isoformat()
                else:
                    update_data["check_out_time"] = now.isoformat()

                if location or device_info:
                    raw = existing.data.get("raw_data") or {}
                    if location:
                        raw["location"] = location
                    if device_info:
                        raw["device_info"] = device_info
                    update_data["raw_data"] = raw

                result = (
                    await db.table("attendance_records")
                    .update(update_data)
                    .eq("id", existing.data["id"])
                    .execute()
                )
            else:
                # Insert new record for today
                data = {
                    "organization_id": org_id,
                    "user_id": employee_id,
                    "platform": "app",
                    "check_date": today,
                    "status": "normal",
                }
                if clock_type == "clock_in":
                    data["check_in_time"] = now.isoformat()
                elif clock_type == "clock_out":
                    data["check_out_time"] = now.isoformat()
                else:
                    data["check_in_time"] = now.isoformat()

                raw_data = {}
                if location:
                    raw_data["location"] = location
                if device_info:
                    raw_data["device_info"] = device_info
                if raw_data:
                    data["raw_data"] = raw_data

                result = await db.table("attendance_records").insert(data).execute()

            if result.data and len(result.data) > 0:
                logger.info(
                    f"打卡成功: org={org_id}, user={employee_id}, type={clock_type}"
                )
                return result.data[0]

            raise RuntimeError("打卡记录创建失败")

        except Exception as e:
            logger.error(f"打卡失败: {e}")
            raise

    async def get_attendance_records(
        self,
        org_id: str,
        employee_id: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        db=None,
    ) -> list[dict]:
        """
        查询考勤记录

        Args:
            org_id: 组织ID
            employee_id: 员工ID（可选）
            start_date: 开始日期（可选）
            end_date: 结束日期（可选）
            db: 数据库客户端

        Returns:
            考勤记录列表
        """
        if not db:
            raise RuntimeError("数据库连接不可用")

        try:
            query = (
                db.table("attendance_records")
                .select("*")
                .eq("organization_id", org_id)
                .order("check_date", desc=True)
            )

            if employee_id:
                query = query.eq("user_id", employee_id)
            if start_date:
                query = query.gte("check_date", start_date)
            if end_date:
                query = query.lte("check_date", end_date)

            result = await query.execute()
            return result.data or []

        except Exception as e:
            logger.error(f"查询考勤记录失败: {e}")
            raise

    async def create_shift_schedule(
        self,
        org_id: str,
        employee_id: str,
        shift_date: str,
        shift_type_id: str,
        created_by: str | None = None,
        db=None,
    ) -> dict:
        """
        创建排班记录

        Args:
            org_id: 组织ID
            employee_id: 员工ID
            shift_date: 排班日期
            shift_type_id: 班次类型ID
            created_by: 创建人ID
            db: 数据库客户端

        Returns:
            排班记录
        """
        if not db:
            raise RuntimeError("数据库连接不可用")

        try:
            # 查询班次类型获取起止时间
            shift_type_result = await (
                db.table("shift_types")
                .select("id, name, start_time, end_time")
                .eq("id", shift_type_id)
                .maybe_single()
                .execute()
            )

            if not shift_type_result.data:
                raise RuntimeError(f"班次类型不存在: {shift_type_id}")

            shift_type = shift_type_result.data

            data = {
                "organization_id": org_id,
                "employee_id": employee_id,
                "shift_date": shift_date,
                "shift_type_id": shift_type_id,
                "start_time": shift_type.get("start_time"),
                "end_time": shift_type.get("end_time"),
                "created_by": created_by,
            }

            result = await db.table("shift_schedules").insert(data).execute()

            if result.data and len(result.data) > 0:
                logger.info(
                    f"排班已创建: org={org_id}, employee={employee_id}, date={shift_date}"
                )
                return result.data[0]

            raise RuntimeError("排班记录创建失败")

        except Exception as e:
            logger.error(f"创建排班失败: {e}")
            raise

    async def list_shift_schedules(
        self,
        org_id: str,
        department_id: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        db=None,
    ) -> list[dict]:
        """
        查询排班列表

        Args:
            org_id: 组织ID
            department_id: 部门ID（TEXT类型，可选）
            start_date: 开始日期（可选）
            end_date: 结束日期（可选）
            db: 数据库客户端

        Returns:
            排班列表
        """
        if not db:
            raise RuntimeError("数据库连接不可用")

        try:
            query = (
                db.table("shift_schedules")
                .select("*, shift_type:shift_types(id, name, color)")
                .eq("organization_id", org_id)
                .order("shift_date", desc=False)
            )

            if department_id:
                query = query.eq("department_id", department_id)
            if start_date:
                query = query.gte("shift_date", start_date)
            if end_date:
                query = query.lte("shift_date", end_date)

            result = await query.execute()
            return result.data or []

        except Exception as e:
            logger.error(f"查询排班列表失败: {e}")
            raise

    async def get_attendance_statistics(
        self,
        org_id: str,
        department_id: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        db=None,
    ) -> dict:
        """
        获取考勤统计数据

        Args:
            org_id: 组织ID
            department_id: 部门ID（TEXT类型，可选）
            start_date: 开始日期（可选）
            end_date: 结束日期（可选）
            db: 数据库客户端

        Returns:
            统计数据
        """
        if not db:
            raise RuntimeError("数据库连接不可用")

        try:
            query = (
                db.table("attendance_records").select("*").eq("organization_id", org_id)
            )

            if department_id:
                query = query.eq("department_id", department_id)
            if start_date:
                query = query.gte("check_date", start_date)
            if end_date:
                query = query.lte("check_date", end_date)

            result = await query.execute()
            records = result.data or []

            total_records = len(records)
            late_count = sum(1 for r in records if r.get("status") == "late")
            early_leave_count = sum(
                1 for r in records if r.get("status") == "early_leave"
            )
            on_time_count = sum(1 for r in records if r.get("status") == "on_time")

            return {
                "total_records": total_records,
                "late_count": late_count,
                "early_leave_count": early_leave_count,
                "on_time_count": on_time_count,
                "on_time_rate": (
                    round(on_time_count / total_records * 100, 2)
                    if total_records > 0
                    else 0
                ),
            }

        except Exception as e:
            logger.error(f"获取考勤统计失败: {e}")
            raise

    async def request_leave(
        self,
        org_id: str,
        employee_id: str,
        leave_type: str,
        start_date: str,
        end_date: str,
        days: float,
        reason: str | None = None,
        db=None,
    ) -> dict:
        """
        提交请假申请

        Args:
            org_id: 组织ID
            employee_id: 员工ID
            leave_type: 请假类型
            start_date: 开始日期
            end_date: 结束日期
            days: 请假天数
            reason: 请假原因
            db: 数据库客户端

        Returns:
            请假记录
        """
        if not db:
            raise RuntimeError("数据库连接不可用")

        try:
            data = {
                "organization_id": org_id,
                "user_id": employee_id,
                "type": leave_type,
                "start_date": start_date,
                "end_date": end_date,
                "days": days,
                "reason": reason,
                "status": "pending",
            }

            result = await db.table("oa_leave_requests").insert(data).execute()

            if result.data and len(result.data) > 0:
                logger.info(
                    f"请假申请已提交: org={org_id}, employee={employee_id}, type={leave_type}"
                )
                return result.data[0]

            raise RuntimeError("请假申请创建失败")

        except Exception as e:
            logger.error(f"提交请假申请失败: {e}")
            raise


attendance_service = AttendanceService()
