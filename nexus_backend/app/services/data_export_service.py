"""
Item 8: Data Export Service
数据导出服务 - 支持审批记录、考勤数据、销售数据的 CSV 导出。
使用 Python 标准库 csv 模块。
"""

import csv
import io
import logging
from datetime import date, datetime
from typing import Any

from app.core.database import supabase

logger = logging.getLogger(__name__)


class DataExportService:
    """
    数据导出服务。

    提供统一的数据导出接口，支持:
    - 审批记录导出
    - 考勤数据导出
    - 销售数据导出
    - 员工数据导出
    - 客户数据导出
    - 通用表数据导出
    """

    # 导出类型 -> 导出配置映射
    EXPORT_CONFIGS: dict[str, dict[str, Any]] = {
        "approvals": {
            "table": "approval_requests",
            "columns": [
                "id",
                "type",
                "amount",
                "description",
                "status",
                "submitted_by",
                "created_at",
                "updated_at",
            ],
            "headers_cn": [
                "审批ID",
                "类型",
                "金额",
                "描述",
                "状态",
                "提交人",
                "创建时间",
                "更新时间",
            ],
            "description": "审批记录",
        },
        "attendance": {
            "table": "attendance_records",
            "columns": [
                "id",
                "user_id",
                "date",
                "check_in",
                "check_out",
                "status",
                "work_hours",
                "notes",
            ],
            "headers_cn": [
                "记录ID",
                "员工ID",
                "日期",
                "签到时间",
                "签退时间",
                "状态",
                "工时",
                "备注",
            ],
            "description": "考勤数据",
        },
        "sales": {
            "table": "sales_records",
            "columns": [
                "id",
                "customer_name",
                "amount",
                "status",
                "sales_rep",
                "product",
                "created_at",
                "closed_at",
            ],
            "headers_cn": [
                "销售ID",
                "客户名称",
                "金额",
                "状态",
                "销售代表",
                "产品",
                "创建时间",
                "成交时间",
            ],
            "description": "销售数据",
        },
        "employees": {
            "table": "users",
            "columns": [
                "id",
                "name",
                "email",
                "department",
                "role",
                "phone",
                "score",
                "total_bonus",
            ],
            "headers_cn": [
                "员工ID",
                "姓名",
                "邮箱",
                "部门",
                "角色",
                "手机号",
                "积分",
                "总奖金",
            ],
            "description": "员工数据",
        },
        "customers": {
            "table": "customers",
            "columns": [
                "id",
                "name",
                "contact_person",
                "phone",
                "email",
                "company",
                "source",
                "notes",
            ],
            "headers_cn": [
                "客户ID",
                "客户名称",
                "联系人",
                "联系电话",
                "邮箱",
                "公司",
                "来源",
                "备注",
            ],
            "description": "客户数据",
        },
    }

    # 导入模板定义
    IMPORT_TEMPLATES: dict[str, dict[str, Any]] = {
        "employees": {
            "headers": ["姓名", "邮箱", "部门", "角色", "手机号"],
            "sample_rows": [
                ["张三", "zhangsan@example.com", "技术部", "employee", "13800138001"],
                ["李四", "lisi@example.com", "销售部", "manager", "13800138002"],
            ],
            "description": "员工批量导入模板",
            "notes": "角色可选值: employee, manager, boss; 邮箱必填且唯一",
        },
        "customers": {
            "headers": ["客户名称", "联系人", "联系电话", "邮箱", "公司", "来源", "备注"],
            "sample_rows": [
                ["ABC科技", "王总", "13900139001", "wang@abc.com", "ABC科技有限公司", "推荐", "重要客户"],
                ["XYZ贸易", "刘经理", "13900139002", "liu@xyz.com", "XYZ贸易公司", "网络", ""],
            ],
            "description": "客户批量导入模板",
            "notes": "客户名称必填; 来源可选: 推荐/网络/电话/展会/其他",
        },
        "attendance": {
            "headers": ["员工邮箱", "日期", "签到时间", "签退时间", "备注"],
            "sample_rows": [
                ["zhangsan@example.com", "2024-01-15", "09:00", "18:00", ""],
                ["lisi@example.com", "2024-01-15", "08:55", "18:30", "加班"],
            ],
            "description": "考勤数据导入模板",
            "notes": "日期格式: YYYY-MM-DD; 时间格式: HH:MM",
        },
        "sales": {
            "headers": ["客户名称", "金额", "产品", "销售代表邮箱", "状态", "备注"],
            "sample_rows": [
                ["ABC科技", "50000", "企业版", "zhangsan@example.com", "进行中", "Q1跟进"],
                ["XYZ贸易", "30000", "标准版", "lisi@example.com", "已成交", ""],
            ],
            "description": "销售数据导入模板",
            "notes": "状态可选: 进行中/已成交/已失败; 金额为数字",
        },
    }

    async def export_to_csv(
        self,
        export_type: str,
        filters: dict[str, Any] | None = None,
        org_id: str | None = None,
        db=None,
    ) -> str:
        """
        根据导出类型导出 CSV 数据。

        Args:
            export_type: 导出类型 (approvals, attendance, sales, employees, customers)
            filters: 可选的过滤条件
            org_id: 组织 ID（用于数据隔离）
            db: 数据库客户端

        Returns:
            CSV 字符串

        Raises:
            ValueError: 不支持的导出类型
        """
        db = db or supabase
        if not db:
            raise ValueError("数据库连接不可用")

        config = self.EXPORT_CONFIGS.get(export_type)
        if not config:
            raise ValueError(f"不支持的导出类型: {export_type}，" f"可选: {', '.join(self.EXPORT_CONFIGS.keys())}")

        try:
            # 构建查询
            columns_str = ", ".join(config["columns"])
            query = db.table(config["table"]).select(columns_str)

            # 应用组织隔离
            if org_id:
                query = query.eq("organization_id", org_id)

            # 应用过滤条件
            if filters:
                query = self._apply_filters(query, filters)

            # 排序和限制
            query = query.order("created_at", desc=True).limit(10000)

            result = await query.execute()
            rows = result.data or []

            # 生成 CSV
            return self._generate_csv(
                headers=config["headers_cn"],
                columns=config["columns"],
                rows=rows,
            )

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Export {export_type} failed: {e}")
            raise ValueError(f"导出失败: {str(e)}")

    async def export_approvals(
        self,
        org_id: str,
        filters: dict[str, Any] | None = None,
        db=None,
    ) -> str:
        """
        导出审批记录（增强版，包含提交人名称）。

        Args:
            org_id: 组织 ID
            filters: 过滤条件 (status, type, date_from, date_to)
            db: 数据库客户端

        Returns:
            CSV 字符串
        """
        db = db or supabase
        if not db:
            raise ValueError("数据库连接不可用")

        try:
            query = (
                db.table("approval_requests")
                .select(
                    "id, type, amount, description, status, "
                    "submitted_by, created_at, updated_at, "
                    "users:submitted_by(name, email)"
                )
                .eq("organization_id", org_id)
            )

            if filters:
                if filters.get("status"):
                    query = query.eq("status", filters["status"])
                if filters.get("type"):
                    query = query.eq("type", filters["type"])
                if filters.get("date_from"):
                    query = query.gte("created_at", filters["date_from"])
                if filters.get("date_to"):
                    query = query.lte("created_at", filters["date_to"])

            query = query.order("created_at", desc=True).limit(10000)
            result = await query.execute()
            rows = result.data or []

            # 展开关联数据
            processed_rows = []
            for row in rows:
                user_info = row.get("users") or {}
                processed_rows.append(
                    {
                        "id": row.get("id", ""),
                        "type": row.get("type", ""),
                        "amount": row.get("amount", 0),
                        "description": row.get("description", ""),
                        "status": row.get("status", ""),
                        "submitter_name": user_info.get("name", ""),
                        "submitter_email": user_info.get("email", ""),
                        "created_at": row.get("created_at", ""),
                        "updated_at": row.get("updated_at", ""),
                    }
                )

            headers = [
                "审批ID",
                "类型",
                "金额",
                "描述",
                "状态",
                "提交人",
                "提交人邮箱",
                "创建时间",
                "更新时间",
            ]
            columns = [
                "id",
                "type",
                "amount",
                "description",
                "status",
                "submitter_name",
                "submitter_email",
                "created_at",
                "updated_at",
            ]

            return self._generate_csv(headers=headers, columns=columns, rows=processed_rows)

        except Exception as e:
            logger.error(f"Export approvals failed: {e}")
            raise ValueError(f"审批记录导出失败: {str(e)}")

    async def export_attendance(
        self,
        org_id: str,
        date_range: dict[str, str] | None = None,
        db=None,
    ) -> str:
        """
        导出考勤数据。

        Args:
            org_id: 组织 ID
            date_range: 日期范围 {"from": "2024-01-01", "to": "2024-01-31"}
            db: 数据库客户端

        Returns:
            CSV 字符串
        """
        db = db or supabase
        if not db:
            raise ValueError("数据库连接不可用")

        try:
            query = (
                db.table("attendance_records")
                .select(
                    "id, user_id, date, check_in, check_out, "
                    "status, work_hours, notes, "
                    "users:user_id(name, email, department)"
                )
                .eq("organization_id", org_id)
            )

            if date_range:
                if date_range.get("from"):
                    query = query.gte("date", date_range["from"])
                if date_range.get("to"):
                    query = query.lte("date", date_range["to"])

            query = query.order("date", desc=True).limit(10000)
            result = await query.execute()
            rows = result.data or []

            processed_rows = []
            for row in rows:
                user_info = row.get("users") or {}
                processed_rows.append(
                    {
                        "name": user_info.get("name", ""),
                        "email": user_info.get("email", ""),
                        "department": user_info.get("department", ""),
                        "date": row.get("date", ""),
                        "check_in": row.get("check_in", ""),
                        "check_out": row.get("check_out", ""),
                        "status": row.get("status", ""),
                        "work_hours": row.get("work_hours", ""),
                        "notes": row.get("notes", ""),
                    }
                )

            headers = [
                "姓名",
                "邮箱",
                "部门",
                "日期",
                "签到时间",
                "签退时间",
                "状态",
                "工时",
                "备注",
            ]
            columns = [
                "name",
                "email",
                "department",
                "date",
                "check_in",
                "check_out",
                "status",
                "work_hours",
                "notes",
            ]

            return self._generate_csv(headers=headers, columns=columns, rows=processed_rows)

        except Exception as e:
            logger.error(f"Export attendance failed: {e}")
            raise ValueError(f"考勤数据导出失败: {str(e)}")

    async def export_sales_data(
        self,
        org_id: str,
        filters: dict[str, Any] | None = None,
        db=None,
    ) -> str:
        """
        导出销售数据。

        Args:
            org_id: 组织 ID
            filters: 过滤条件 (status, date_from, date_to, sales_rep)
            db: 数据库客户端

        Returns:
            CSV 字符串
        """
        db = db or supabase
        if not db:
            raise ValueError("数据库连接不可用")

        try:
            query = (
                db.table("sales_records")
                .select(
                    "id, customer_name, amount, status, product, "
                    "created_at, closed_at, notes, "
                    "users:sales_rep(name, email)"
                )
                .eq("organization_id", org_id)
            )

            if filters:
                if filters.get("status"):
                    query = query.eq("status", filters["status"])
                if filters.get("date_from"):
                    query = query.gte("created_at", filters["date_from"])
                if filters.get("date_to"):
                    query = query.lte("created_at", filters["date_to"])
                if filters.get("sales_rep"):
                    query = query.eq("sales_rep", filters["sales_rep"])

            query = query.order("created_at", desc=True).limit(10000)
            result = await query.execute()
            rows = result.data or []

            processed_rows = []
            for row in rows:
                user_info = row.get("users") or {}
                processed_rows.append(
                    {
                        "id": row.get("id", ""),
                        "customer_name": row.get("customer_name", ""),
                        "amount": row.get("amount", 0),
                        "status": row.get("status", ""),
                        "product": row.get("product", ""),
                        "sales_rep_name": user_info.get("name", ""),
                        "sales_rep_email": user_info.get("email", ""),
                        "created_at": row.get("created_at", ""),
                        "closed_at": row.get("closed_at", ""),
                        "notes": row.get("notes", ""),
                    }
                )

            headers = [
                "销售ID",
                "客户名称",
                "金额",
                "状态",
                "产品",
                "销售代表",
                "代表邮箱",
                "创建时间",
                "成交时间",
                "备注",
            ]
            columns = [
                "id",
                "customer_name",
                "amount",
                "status",
                "product",
                "sales_rep_name",
                "sales_rep_email",
                "created_at",
                "closed_at",
                "notes",
            ]

            return self._generate_csv(headers=headers, columns=columns, rows=processed_rows)

        except Exception as e:
            logger.error(f"Export sales data failed: {e}")
            raise ValueError(f"销售数据导出失败: {str(e)}")

    def generate_template(self, template_type: str) -> str:
        """
        生成导入模板 CSV（含示例数据行）。

        Args:
            template_type: 模板类型

        Returns:
            CSV 字符串（含表头和示例行）

        Raises:
            ValueError: 不支持的模板类型
        """
        template = self.IMPORT_TEMPLATES.get(template_type)
        if not template:
            raise ValueError(f"不支持的模板类型: {template_type}，" f"可选: {', '.join(self.IMPORT_TEMPLATES.keys())}")

        output = io.StringIO()
        # 添加 BOM 以支持 Excel 正确识别 UTF-8
        output.write("\ufeff")

        writer = csv.writer(output)

        # 写入表头
        writer.writerow(template["headers"])

        # 写入示例行
        for sample in template.get("sample_rows", []):
            writer.writerow(sample)

        return output.getvalue()

    def get_available_templates(self) -> list[dict[str, Any]]:
        """
        获取所有可用的导入模板信息。

        Returns:
            模板信息列表
        """
        return [
            {
                "type": key,
                "description": tmpl["description"],
                "headers": tmpl["headers"],
                "notes": tmpl.get("notes", ""),
            }
            for key, tmpl in self.IMPORT_TEMPLATES.items()
        ]

    def get_available_exports(self) -> list[dict[str, Any]]:
        """
        获取所有可用的导出类型信息。

        Returns:
            导出类型信息列表
        """
        return [
            {
                "type": key,
                "description": cfg["description"],
                "columns": cfg["headers_cn"],
            }
            for key, cfg in self.EXPORT_CONFIGS.items()
        ]

    # ============== 内部工具 ==============

    def _generate_csv(
        self,
        headers: list[str],
        columns: list[str],
        rows: list[dict[str, Any]],
    ) -> str:
        """
        生成 CSV 字符串。

        Args:
            headers: CSV 表头（中文）
            columns: 数据字段名
            rows: 数据行列表

        Returns:
            CSV 字符串
        """
        output = io.StringIO()
        # BOM for Excel UTF-8 compatibility
        output.write("\ufeff")

        writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)

        # 写入表头
        writer.writerow(headers)

        # 写入数据行
        for row in rows:
            csv_row = []
            for col in columns:
                value = row.get(col, "")
                # 处理 None 值
                if value is None:
                    value = ""
                # 处理日期时间
                elif isinstance(value, datetime | date):
                    value = value.isoformat()
                # 处理数字
                elif isinstance(value, int | float):
                    value = str(value)
                csv_row.append(str(value))
            writer.writerow(csv_row)

        return output.getvalue()

    def _apply_filters(self, query, filters: dict[str, Any]):
        """
        对查询应用通用过滤条件。

        Args:
            query: PostgREST 查询对象
            filters: 过滤条件字典

        Returns:
            带过滤的查询对象
        """
        for key, value in filters.items():
            if value is None or value == "":
                continue

            if key == "date_from":
                query = query.gte("created_at", value)
            elif key == "date_to":
                query = query.lte("created_at", value)
            elif key == "status":
                query = query.eq("status", value)
            elif key == "type":
                query = query.eq("type", value)
            elif key.endswith("_id"):
                query = query.eq(key, value)

        return query


# 全局单例
data_export_service = DataExportService()
