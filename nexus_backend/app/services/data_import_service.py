"""
Item 8: Data Import Service (Enhanced)
增强版数据导入服务 - 支持多种数据类型的批量导入和预验证。

在原有 ImportService 基础上提供:
- 统一的导入接口（按类型分发）
- 完整的预验证（不写入数据库）
- 列映射和数据转换
- 详细的错误报告
"""

import csv
import io
import re
import logging
from typing import Dict, List, Any, Optional, Tuple
from app.core.database import supabase

logger = logging.getLogger(__name__)


class DataImportService:
    """
    增强版数据导入服务。

    支持类型:
    - employees: 员工数据
    - customers: 客户数据
    - attendance: 考勤数据
    - sales: 销售数据

    特性:
    - CSV 解析（支持 UTF-8 和 GBK 编码）
    - 自动列名映射（中英文表头兼容）
    - 预验证（返回所有错误但不写入）
    - 批量插入（带错误容忍）
    """

    # 列映射表（中文 -> 英文）
    COLUMN_MAPPINGS: Dict[str, Dict[str, str]] = {
        "employees": {
            "姓名": "name", "name": "name",
            "邮箱": "email", "email": "email",
            "部门": "department", "department": "department",
            "角色": "role", "role": "role",
            "手机号": "phone", "phone": "phone",
        },
        "customers": {
            "客户名称": "name", "name": "name",
            "联系人": "contact_person", "contact_person": "contact_person",
            "联系电话": "phone", "phone": "phone",
            "邮箱": "email", "email": "email",
            "公司": "company", "company": "company",
            "来源": "source", "source": "source",
            "备注": "notes", "notes": "notes",
        },
        "attendance": {
            "员工邮箱": "email", "email": "email",
            "日期": "date", "date": "date",
            "签到时间": "check_in", "check_in": "check_in",
            "签退时间": "check_out", "check_out": "check_out",
            "备注": "notes", "notes": "notes",
        },
        "sales": {
            "客户名称": "customer_name", "customer_name": "customer_name",
            "金额": "amount", "amount": "amount",
            "产品": "product", "product": "product",
            "销售代表邮箱": "sales_rep_email", "sales_rep_email": "sales_rep_email",
            "状态": "status", "status": "status",
            "备注": "notes", "notes": "notes",
        },
    }

    # 必填字段
    REQUIRED_FIELDS: Dict[str, List[str]] = {
        "employees": ["name", "email"],
        "customers": ["name"],
        "attendance": ["email", "date", "check_in"],
        "sales": ["customer_name", "amount"],
    }

    # 验证规则
    VALID_ROLES = {"employee", "manager", "boss", "founder"}
    VALID_SOURCES = {"推荐", "网络", "电话", "展会", "其他"}
    VALID_SALES_STATUS = {"进行中", "已成交", "已失败"}

    async def import_csv(
        self,
        import_type: str,
        csv_content: str,
        org_id: str,
        user_id: str,
        column_mapping: Optional[Dict[str, str]] = None,
        db=None,
    ) -> Dict[str, Any]:
        """
        导入 CSV 数据。

        Args:
            import_type: 导入类型
            csv_content: CSV 字符串内容
            org_id: 组织 ID
            user_id: 操作用户 ID
            column_mapping: 可选的自定义列映射
            db: 数据库客户端

        Returns:
            导入结果统计
        """
        db = db or supabase
        if not db:
            return self._error_result("数据库连接不可用")

        if import_type not in self.COLUMN_MAPPINGS:
            return self._error_result(
                f"不支持的导入类型: {import_type}，"
                f"可选: {', '.join(self.COLUMN_MAPPINGS.keys())}"
            )

        try:
            # 1. 解析 CSV
            rows = self._parse_csv_content(csv_content)
            if not rows:
                return self._error_result("CSV 文件为空或无法解析")

            # 2. 映射列名
            mapping = column_mapping or self.COLUMN_MAPPINGS.get(import_type, {})
            normalized_rows = self._normalize_rows(rows, mapping)

            # 3. 验证数据
            validation_errors = self._validate_rows(import_type, normalized_rows)

            # 4. 执行导入（跳过有错误的行）
            error_row_indices = {e["row"] for e in validation_errors}

            success_count = 0
            skip_count = 0
            import_errors = list(validation_errors)  # copy

            for idx, row in enumerate(normalized_rows, start=2):
                if idx in error_row_indices:
                    continue

                try:
                    imported = await self._import_single_row(
                        import_type, row, org_id, user_id, db
                    )
                    if imported:
                        success_count += 1
                    else:
                        skip_count += 1
                except Exception as e:
                    import_errors.append({
                        "row": idx,
                        "field": "unknown",
                        "reason": str(e),
                        "data": row,
                    })

            return {
                "success_count": success_count,
                "skip_count": skip_count,
                "error_count": len(import_errors),
                "total_rows": len(normalized_rows),
                "errors": import_errors[:50],  # 最多返回50条错误
            }

        except Exception as e:
            logger.error(f"Import {import_type} failed: {e}")
            return self._error_result(f"导入失败: {str(e)}")

    async def validate_import_data(
        self,
        import_type: str,
        csv_content: str,
        column_mapping: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        预验证导入数据（不写入数据库）。

        Args:
            import_type: 导入类型
            csv_content: CSV 字符串内容
            column_mapping: 可选的自定义列映射

        Returns:
            验证结果，包含错误列表和统计信息
        """
        if import_type not in self.COLUMN_MAPPINGS:
            return {
                "valid": False,
                "total_rows": 0,
                "error_count": 1,
                "errors": [{
                    "row": 0,
                    "field": "import_type",
                    "reason": f"不支持的导入类型: {import_type}",
                }],
            }

        try:
            rows = self._parse_csv_content(csv_content)
            if not rows:
                return {
                    "valid": False,
                    "total_rows": 0,
                    "error_count": 1,
                    "errors": [{"row": 0, "field": "file", "reason": "CSV 文件为空"}],
                }

            mapping = column_mapping or self.COLUMN_MAPPINGS.get(import_type, {})
            normalized_rows = self._normalize_rows(rows, mapping)
            errors = self._validate_rows(import_type, normalized_rows)

            # 预览前5行有效数据
            error_indices = {e["row"] for e in errors}
            preview_rows = []
            for idx, row in enumerate(normalized_rows, start=2):
                if idx not in error_indices and len(preview_rows) < 5:
                    preview_rows.append(row)

            return {
                "valid": len(errors) == 0,
                "total_rows": len(normalized_rows),
                "valid_rows": len(normalized_rows) - len(errors),
                "error_count": len(errors),
                "errors": errors[:50],
                "preview": preview_rows,
                "detected_columns": list(normalized_rows[0].keys()) if normalized_rows else [],
            }

        except Exception as e:
            logger.error(f"Validation for {import_type} failed: {e}")
            return {
                "valid": False,
                "total_rows": 0,
                "error_count": 1,
                "errors": [{"row": 0, "field": "file", "reason": str(e)}],
            }

    def get_import_templates(self) -> List[Dict[str, Any]]:
        """
        获取可用的导入模板列表。

        Returns:
            模板信息列表
        """
        return [
            {
                "type": import_type,
                "required_fields": self.REQUIRED_FIELDS.get(import_type, []),
                "all_fields": list(set(mapping.values())),
            }
            for import_type, mapping in self.COLUMN_MAPPINGS.items()
        ]

    # ============== CSV 解析 ==============

    def _parse_csv_content(self, csv_content: str) -> List[Dict[str, str]]:
        """
        解析 CSV 字符串内容。

        Args:
            csv_content: CSV 字符串（可能包含 BOM）

        Returns:
            解析后的数据行列表
        """
        # 移除 BOM
        if csv_content.startswith('\ufeff'):
            csv_content = csv_content[1:]

        text_io = io.StringIO(csv_content)
        reader = csv.DictReader(text_io)

        data = []
        for row in reader:
            # 过滤完全空行
            if any(v and v.strip() for v in row.values()):
                # 清理值
                cleaned = {
                    k.strip(): (v.strip() if v else "")
                    for k, v in row.items()
                    if k  # 忽略空列名
                }
                data.append(cleaned)

        return data

    def _normalize_rows(
        self,
        rows: List[Dict[str, str]],
        mapping: Dict[str, str],
    ) -> List[Dict[str, str]]:
        """
        使用列映射标准化数据行。

        Args:
            rows: 原始数据行
            mapping: 列名映射表

        Returns:
            标准化后的数据行
        """
        normalized = []
        for row in rows:
            new_row = {}
            for key, value in row.items():
                mapped_key = mapping.get(key, key)
                new_row[mapped_key] = value
            normalized.append(new_row)
        return normalized

    # ============== 验证 ==============

    def _validate_rows(
        self, import_type: str, rows: List[Dict[str, str]]
    ) -> List[Dict[str, Any]]:
        """
        验证所有数据行。

        Args:
            import_type: 导入类型
            rows: 标准化后的数据行

        Returns:
            错误列表
        """
        errors = []
        required = self.REQUIRED_FIELDS.get(import_type, [])
        seen_keys: Dict[str, int] = {}  # 重复检测

        for idx, row in enumerate(rows, start=2):
            # 必填字段检查
            for field_name in required:
                value = row.get(field_name, "").strip()
                if not value:
                    errors.append({
                        "row": idx,
                        "field": field_name,
                        "reason": f"必填字段 {field_name} 为空",
                        "data": row,
                    })

            # 类型特定验证
            type_errors = self._validate_by_type(import_type, row, idx)
            errors.extend(type_errors)

            # 重复检测
            dup_error = self._check_duplicate(import_type, row, idx, seen_keys)
            if dup_error:
                errors.append(dup_error)

        return errors

    def _validate_by_type(
        self, import_type: str, row: Dict[str, str], row_num: int
    ) -> List[Dict[str, Any]]:
        """按导入类型执行特定验证"""
        errors = []

        if import_type == "employees":
            errors.extend(self._validate_employee_row(row, row_num))
        elif import_type == "customers":
            errors.extend(self._validate_customer_row(row, row_num))
        elif import_type == "attendance":
            errors.extend(self._validate_attendance_row(row, row_num))
        elif import_type == "sales":
            errors.extend(self._validate_sales_row(row, row_num))

        return errors

    def _validate_employee_row(
        self, row: Dict[str, str], row_num: int
    ) -> List[Dict[str, Any]]:
        """验证员工数据行"""
        errors = []
        email = row.get("email", "").strip()
        if email and not self._is_valid_email(email):
            errors.append({
                "row": row_num, "field": "email",
                "reason": f"邮箱格式无效: {email}", "data": row,
            })

        role = row.get("role", "").strip()
        if role and role not in self.VALID_ROLES:
            errors.append({
                "row": row_num, "field": "role",
                "reason": f"角色无效: {role}，可选: {', '.join(self.VALID_ROLES)}",
                "data": row,
            })

        phone = row.get("phone", "").strip()
        if phone and not self._is_valid_phone(phone):
            errors.append({
                "row": row_num, "field": "phone",
                "reason": f"手机号格式无效: {phone}", "data": row,
            })

        return errors

    def _validate_customer_row(
        self, row: Dict[str, str], row_num: int
    ) -> List[Dict[str, Any]]:
        """验证客户数据行"""
        errors = []
        email = row.get("email", "").strip()
        if email and not self._is_valid_email(email):
            errors.append({
                "row": row_num, "field": "email",
                "reason": f"邮箱格式无效: {email}", "data": row,
            })

        phone = row.get("phone", "").strip()
        if phone and not self._is_valid_phone(phone):
            errors.append({
                "row": row_num, "field": "phone",
                "reason": f"联系电话格式无效: {phone}", "data": row,
            })

        return errors

    def _validate_attendance_row(
        self, row: Dict[str, str], row_num: int
    ) -> List[Dict[str, Any]]:
        """验证考勤数据行"""
        errors = []
        date_str = row.get("date", "").strip()
        if date_str and not self._is_valid_date(date_str):
            errors.append({
                "row": row_num, "field": "date",
                "reason": f"日期格式无效: {date_str}，应为 YYYY-MM-DD", "data": row,
            })

        for time_field in ["check_in", "check_out"]:
            time_str = row.get(time_field, "").strip()
            if time_str and not self._is_valid_time(time_str):
                errors.append({
                    "row": row_num, "field": time_field,
                    "reason": f"时间格式无效: {time_str}，应为 HH:MM", "data": row,
                })

        return errors

    def _validate_sales_row(
        self, row: Dict[str, str], row_num: int
    ) -> List[Dict[str, Any]]:
        """验证销售数据行"""
        errors = []
        amount = row.get("amount", "").strip()
        if amount:
            try:
                float(amount)
            except ValueError:
                errors.append({
                    "row": row_num, "field": "amount",
                    "reason": f"金额必须为数字: {amount}", "data": row,
                })

        status = row.get("status", "").strip()
        if status and status not in self.VALID_SALES_STATUS:
            errors.append({
                "row": row_num, "field": "status",
                "reason": f"状态无效: {status}，可选: {', '.join(self.VALID_SALES_STATUS)}",
                "data": row,
            })

        return errors

    def _check_duplicate(
        self,
        import_type: str,
        row: Dict[str, str],
        row_num: int,
        seen: Dict[str, int],
    ) -> Optional[Dict[str, Any]]:
        """检查文件内部重复"""
        if import_type == "employees":
            key = row.get("email", "").strip().lower()
        elif import_type == "customers":
            name = row.get("name", "").strip()
            company = row.get("company", "").strip()
            key = f"{name}|{company}"
        elif import_type == "attendance":
            email = row.get("email", "").strip().lower()
            date_str = row.get("date", "").strip()
            key = f"{email}|{date_str}"
        elif import_type == "sales":
            customer = row.get("customer_name", "").strip()
            amount = row.get("amount", "").strip()
            key = f"{customer}|{amount}"
        else:
            return None

        if not key or key == "|":
            return None

        if key in seen:
            return {
                "row": row_num,
                "field": "duplicate",
                "reason": f"与第 {seen[key]} 行重复",
                "data": row,
            }

        seen[key] = row_num
        return None

    # ============== 数据库写入 ==============

    async def _import_single_row(
        self,
        import_type: str,
        row: Dict[str, str],
        org_id: str,
        user_id: str,
        db,
    ) -> bool:
        """
        导入单行数据到数据库。

        Args:
            import_type: 导入类型
            row: 标准化的数据行
            org_id: 组织 ID
            user_id: 操作用户 ID
            db: 数据库客户端

        Returns:
            True 如果成功导入，False 如果跳过（已存在）
        """
        if import_type == "employees":
            return await self._import_employee(row, org_id, db)
        elif import_type == "customers":
            return await self._import_customer(row, org_id, user_id, db)
        elif import_type == "attendance":
            return await self._import_attendance(row, org_id, db)
        elif import_type == "sales":
            return await self._import_sale(row, org_id, user_id, db)
        else:
            raise ValueError(f"Unknown import type: {import_type}")

    async def _import_employee(
        self, row: Dict[str, str], org_id: str, db
    ) -> bool:
        """导入单条员工记录"""
        email = row.get("email", "").strip()
        existing = await db.table("users").select("id").eq(
            "email", email
        ).maybe_single().execute()

        if existing.data:
            return False  # 跳过

        await db.table("users").insert({
            "name": row.get("name", "").strip(),
            "email": email,
            "department": row.get("department", "").strip() or None,
            "role": row.get("role", "employee").strip(),
            "phone": row.get("phone", "").strip() or None,
            "organization_id": org_id,
            "password": "Nexus@123",
            "score": 0,
            "total_bonus": 0,
        }).execute()
        return True

    async def _import_customer(
        self, row: Dict[str, str], org_id: str, user_id: str, db
    ) -> bool:
        """导入单条客户记录"""
        name = row.get("name", "").strip()
        company = row.get("company", "").strip()

        query = db.table("customers").select("id").eq("name", name)
        if company:
            query = query.eq("company", company)
        existing = await query.maybe_single().execute()

        if existing.data:
            return False

        await db.table("customers").insert({
            "name": name,
            "contact_person": row.get("contact_person", "").strip() or None,
            "phone": row.get("phone", "").strip() or None,
            "email": row.get("email", "").strip() or None,
            "company": company or None,
            "source": row.get("source", "批量导入").strip(),
            "notes": row.get("notes", "").strip() or None,
            "created_by": user_id,
            "organization_id": org_id,
        }).execute()
        return True

    async def _import_attendance(
        self, row: Dict[str, str], org_id: str, db
    ) -> bool:
        """导入单条考勤记录"""
        email = row.get("email", "").strip()

        # 查找用户 ID
        user_res = await db.table("users").select("id").eq(
            "email", email
        ).maybe_single().execute()

        if not user_res.data:
            raise ValueError(f"未找到邮箱对应的用户: {email}")

        user_id = user_res.data["id"]
        date_str = row.get("date", "").strip()

        # 检查是否已存在
        existing = await db.table("attendance_records").select("id").eq(
            "user_id", user_id
        ).eq("date", date_str).maybe_single().execute()

        if existing.data:
            return False

        await db.table("attendance_records").insert({
            "user_id": user_id,
            "date": date_str,
            "check_in": row.get("check_in", "").strip() or None,
            "check_out": row.get("check_out", "").strip() or None,
            "notes": row.get("notes", "").strip() or None,
            "status": "normal",
            "organization_id": org_id,
        }).execute()
        return True

    async def _import_sale(
        self, row: Dict[str, str], org_id: str, user_id: str, db
    ) -> bool:
        """导入单条销售记录"""
        customer_name = row.get("customer_name", "").strip()
        amount_str = row.get("amount", "0").strip()
        amount = float(amount_str) if amount_str else 0

        # 查找销售代表
        sales_rep_id = user_id
        rep_email = row.get("sales_rep_email", "").strip()
        if rep_email:
            rep_res = await db.table("users").select("id").eq(
                "email", rep_email
            ).maybe_single().execute()
            if rep_res.data:
                sales_rep_id = rep_res.data["id"]

        await db.table("sales_records").insert({
            "customer_name": customer_name,
            "amount": amount,
            "product": row.get("product", "").strip() or None,
            "sales_rep": sales_rep_id,
            "status": row.get("status", "进行中").strip(),
            "notes": row.get("notes", "").strip() or None,
            "organization_id": org_id,
        }).execute()
        return True

    # ============== 工具方法 ==============

    @staticmethod
    def _is_valid_email(email: str) -> bool:
        return bool(re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", email))

    @staticmethod
    def _is_valid_phone(phone: str) -> bool:
        return bool(re.match(r"^1\d{10}$", phone))

    @staticmethod
    def _is_valid_date(date_str: str) -> bool:
        return bool(re.match(r"^\d{4}-\d{2}-\d{2}$", date_str))

    @staticmethod
    def _is_valid_time(time_str: str) -> bool:
        return bool(re.match(r"^\d{2}:\d{2}$", time_str))

    @staticmethod
    def _error_result(message: str) -> Dict[str, Any]:
        return {
            "success_count": 0,
            "skip_count": 0,
            "error_count": 1,
            "total_rows": 0,
            "errors": [{"row": 0, "field": "system", "reason": message}],
        }


# 全局单例
data_import_service = DataImportService()
