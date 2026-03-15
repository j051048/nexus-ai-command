"""
组织架构工具集
提供部门、职位、员工管理功能
"""

import logging
from typing import Any

from app.services.organization_service import organization_service

from .base_tool import BaseTool
from ._shared import _get_client, _validate_uuid

logger = logging.getLogger(__name__)


def _get_org_id(config: dict = None) -> str | None:
    return config.get("org_id") if config else None


# ============================================================================
# 部门管理工具
# ============================================================================


class ListDepartmentsTool(BaseTool):
    """查询部门列表"""

    name = "list_departments"
    description = "查询组织的部门列表，支持查询子部门。当用户说'查看部门'、'部门列表'、'有哪些部门'时调用。"

    parameters = {
        "type": "object",
        "properties": {
            "parent_id": {
                "type": "string",
                "description": "父部门ID（可选，查询子部门）",
            },
        },
        "required": [],
    }

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        client = _get_client(config)
        org_id = _get_org_id(config)
        if not org_id:
            return "❌ 无法获取组织信息，请确保已正确登录。"

        parent_id = args.get("parent_id")

        if parent_id and (err := _validate_uuid(parent_id, "parent_id")):
            return f"❌ {err}"

        try:
            departments = await organization_service.list_departments(
                org_id=org_id,
                parent_id=parent_id,
                db=client,
            )

            if not departments:
                return "当前暂无部门记录。您可以说「创建部门」来添加新部门。"

            lines = [f"📋 共找到 {len(departments)} 个部门:\n"]
            for dept in departments:
                manager = dept.get("manager")
                manager_name = manager.get("name") if manager else "未设置"
                lines.append(f"- **{dept.get('name')}** | 负责人: {manager_name} | ID: {dept['id'][:8]}...")

            return "\n".join(lines)

        except Exception as e:
            logger.error(f"查询部门列表失败: {e}")
            return f"❌ 查询部门列表失败: {str(e)}"


class CreateDepartmentTool(BaseTool):
    """创建部门"""

    name = "create_department"
    description = "创建新部门。当用户说'创建部门'、'新建部门'、'添加部门'时调用。"
    required_role = "admin"

    parameters = {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "部门名称",
                "maxLength": 100,
            },
            "parent_id": {
                "type": "string",
                "description": "父部门ID（可选）",
            },
            "manager_id": {
                "type": "string",
                "description": "部门负责人ID（可选）",
            },
        },
        "required": ["name"],
    }

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        client = _get_client(config)
        org_id = _get_org_id(config)
        if not org_id:
            return "❌ 无法获取组织信息，请确保已正确登录。"

        name = args.get("name", "").strip()
        parent_id = args.get("parent_id")
        manager_id = args.get("manager_id")

        if not name:
            return "❌ 部门名称不能为空"

        if parent_id and (err := _validate_uuid(parent_id, "parent_id")):
            return f"❌ {err}"

        if manager_id and (err := _validate_uuid(manager_id, "manager_id")):
            return f"❌ {err}"

        try:
            department = await organization_service.create_department(
                org_id=org_id,
                name=name,
                parent_id=parent_id,
                manager_id=manager_id,
                db=client,
            )

            return (
                f"✅ 部门创建成功！\n\n"
                f"- 名称: {department.get('name')}\n"
                f"- ID: {department['id']}\n\n"
                f"您可以继续添加子部门或员工。"
            )

        except Exception as e:
            logger.error(f"创建部门失败: {e}")
            return f"❌ 创建部门失败: {str(e)}"


class UpdateDepartmentTool(BaseTool):
    """更新部门信息"""

    name = "update_department"
    description = "更新部门信息（名称、负责人、状态等）。当用户说'更新部门'、'修改部门'、'设置部门负责人'时调用。"
    required_role = "admin"

    parameters = {
        "type": "object",
        "properties": {
            "department_id": {
                "type": "string",
                "description": "部门ID",
            },
            "name": {
                "type": "string",
                "description": "部门名称（可选）",
                "maxLength": 100,
            },
            "manager_id": {
                "type": "string",
                "description": "部门负责人ID（可选）",
            },
            "status": {
                "type": "string",
                "description": "部门状态（可选）",
                "enum": ["active", "merged", "dissolved"],
            },
        },
        "required": ["department_id"],
    }

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        client = _get_client(config)
        org_id = _get_org_id(config)
        if not org_id:
            return "❌ 无法获取组织信息，请确保已正确登录。"

        department_id = args.get("department_id")

        if err := _validate_uuid(department_id, "department_id"):
            return f"❌ {err}"

        updates = {}
        if args.get("name"):
            updates["name"] = args["name"].strip()
        if args.get("manager_id"):
            if err := _validate_uuid(args["manager_id"], "manager_id"):
                return f"❌ {err}"
            updates["manager_id"] = args["manager_id"]
        if args.get("status"):
            updates["status"] = args["status"]

        if not updates:
            return "❌ 请提供至少一个要更新的字段"

        try:
            department = await organization_service.update_department(
                department_id=department_id,
                updates=updates,
                db=client,
            )

            return f"✅ 部门已更新: {department.get('name')}"

        except Exception as e:
            logger.error(f"更新部门失败: {e}")
            return f"❌ 更新部门失败: {str(e)}"


# ============================================================================
# 员工管理工具
# ============================================================================


class ListEmployeesTool(BaseTool):
    """查询员工列表"""

    name = "list_employees"
    description = "查询员工花名册，支持按部门、职位、状态筛选。当用户说'查看员工'、'员工列表'、'有哪些员工'时调用。"

    parameters = {
        "type": "object",
        "properties": {
            "department_id": {
                "type": "string",
                "description": "部门ID（可选）",
            },
            "position_id": {
                "type": "string",
                "description": "职位ID（可选）",
            },
            "status": {
                "type": "string",
                "description": "员工状态（可选）",
                "enum": ["active", "resigned", "suspended"],
            },
            "search": {
                "type": "string",
                "description": "搜索关键词（姓名/手机/邮箱）",
                "maxLength": 100,
            },
        },
        "required": [],
    }

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        client = _get_client(config)
        org_id = _get_org_id(config)
        if not org_id:
            return "❌ 无法获取组织信息，请确保已正确登录。"

        filters = {}
        if args.get("department_id"):
            if err := _validate_uuid(args["department_id"], "department_id"):
                return f"❌ {err}"
            filters["department_id"] = args["department_id"]
        if args.get("position_id"):
            if err := _validate_uuid(args["position_id"], "position_id"):
                return f"❌ {err}"
            filters["position_id"] = args["position_id"]
        if args.get("status"):
            filters["status"] = args["status"]
        if args.get("search"):
            filters["search"] = args["search"]

        try:
            employees = await organization_service.list_employees(
                org_id=org_id,
                filters=filters or None,
                db=client,
            )

            if not employees:
                return "当前暂无员工记录。您可以说「创建员工」来添加新员工。"

            lines = [f"📋 共找到 {len(employees)} 名员工:\n"]
            for emp in employees:
                pos = emp.get("position", {})
                dept_id = emp.get("department_id", "未分配")
                pos_name = pos.get("name", "未设置") if pos else "未设置"
                status_map = {"active": "在职", "resigned": "离职", "suspended": "停职"}
                status = status_map.get(emp.get("status", ""), emp.get("status", ""))

                lines.append(
                    f"- **{emp.get('name')}** | 部门: {dept_id[:8]}... - {pos_name} | "
                    f"状态: {status} | 手机: {emp.get('phone', '未填写')} | ID: {emp['id'][:8]}..."
                )

            return "\n".join(lines)

        except Exception as e:
            logger.error(f"查询员工列表失败: {e}")
            return f"❌ 查询员工列表失败: {str(e)}"


class GetEmployeeDetailTool(BaseTool):
    """获取员工详情"""

    name = "get_employee_detail"
    description = "获取员工详细信息。当用户说'查看员工详情'、'员工信息'时调用。"

    parameters = {
        "type": "object",
        "properties": {
            "employee_id": {
                "type": "string",
                "description": "员工ID",
            },
        },
        "required": ["employee_id"],
    }

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        client = _get_client(config)
        employee_id = args.get("employee_id")

        if err := _validate_uuid(employee_id, "employee_id"):
            return f"❌ {err}"

        try:
            employee = await organization_service.get_employee_detail(
                employee_id=employee_id,
                db=client,
            )

            if not employee:
                return f"❌ 未找到ID为 {employee_id} 的员工。"

            dept_id = employee.get("department_id", "未分配")
            pos = employee.get("position", {})
            pos_name = pos.get("name", "未设置") if pos else "未设置"
            status_map = {"active": "在职", "resigned": "离职", "suspended": "停职"}
            status = status_map.get(employee.get("status", ""), employee.get("status", ""))

            return (
                f"👤 员工详情:\n\n"
                f"- 姓名: {employee.get('name')}\n"
                f"- 部门ID: {dept_id}\n"
                f"- 职位: {pos_name}\n"
                f"- 状态: {status}\n"
                f"- 手机: {employee.get('phone', '未填写')}\n"
                f"- 邮箱: {employee.get('email', '未填写')}\n"
                f"- 入职日期: {employee.get('hire_date', '未填写')}\n"
                f"- ID: {employee['id']}"
            )

        except Exception as e:
            logger.error(f"获取员工详情失败: {e}")
            return f"❌ 获取员工详情失败: {str(e)}"


class CreateEmployeeTool(BaseTool):
    """创建员工"""

    name = "create_employee"
    description = "创建新员工（入职登记）。当用户说'创建员工'、'新员工入职'、'录入员工'时调用。"
    required_role = "admin"

    parameters = {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "员工姓名",
                "maxLength": 50,
            },
            "department_id": {
                "type": "string",
                "description": "部门ID",
            },
            "position_id": {
                "type": "string",
                "description": "职位ID（可选）",
            },
            "phone": {
                "type": "string",
                "description": "手机号（可选）",
                "maxLength": 20,
            },
            "email": {
                "type": "string",
                "description": "邮箱（可选）",
                "maxLength": 100,
            },
            "hire_date": {
                "type": "string",
                "description": "入职日期 YYYY-MM-DD（可选）",
            },
        },
        "required": ["name", "department_id"],
    }

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        client = _get_client(config)
        org_id = _get_org_id(config)
        if not org_id:
            return "❌ 无法获取组织信息，请确保已正确登录。"

        name = args.get("name", "").strip()
        department_id = args.get("department_id")

        if not name:
            return "❌ 员工姓名不能为空"

        if err := _validate_uuid(department_id, "department_id"):
            return f"❌ {err}"

        if args.get("position_id") and (err := _validate_uuid(args["position_id"], "position_id")):
            return f"❌ {err}"

        data = {
            "name": name,
            "department_id": department_id,
        }

        for field in ["position_id", "phone", "email", "hire_date"]:
            if args.get(field):
                data[field] = args[field]

        try:
            employee = await organization_service.create_employee(
                org_id=org_id,
                data=data,
                db=client,
            )

            return (
                f"✅ 员工创建成功！\n\n"
                f"- 姓名: {employee.get('name')}\n"
                f"- 手机: {employee.get('phone', '未填写')}\n"
                f"- ID: {employee['id']}\n\n"
                f"您可以继续更新员工详情。"
            )

        except Exception as e:
            logger.error(f"创建员工失败: {e}")
            return f"❌ 创建员工失败: {str(e)}"


class UpdateEmployeeTool(BaseTool):
    """更新员工信息"""

    name = "update_employee"
    description = "更新员工信息（调岗、离职、信息变更等）。当用户说'更新员工'、'员工调岗'、'员工离职'时调用。"
    required_role = "admin"

    parameters = {
        "type": "object",
        "properties": {
            "employee_id": {
                "type": "string",
                "description": "员工ID",
            },
            "department_id": {
                "type": "string",
                "description": "部门ID（可选）",
            },
            "position_id": {
                "type": "string",
                "description": "职位ID（可选）",
            },
            "status": {
                "type": "string",
                "description": "员工状态（可选）",
                "enum": ["active", "resigned", "suspended"],
            },
            "phone": {
                "type": "string",
                "description": "手机号（可选）",
                "maxLength": 20,
            },
            "email": {
                "type": "string",
                "description": "邮箱（可选）",
                "maxLength": 100,
            },
        },
        "required": ["employee_id"],
    }

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        client = _get_client(config)
        employee_id = args.get("employee_id")

        if err := _validate_uuid(employee_id, "employee_id"):
            return f"❌ {err}"

        updates = {}
        if args.get("department_id"):
            if err := _validate_uuid(args["department_id"], "department_id"):
                return f"❌ {err}"
            updates["department_id"] = args["department_id"]
        if args.get("position_id"):
            if err := _validate_uuid(args["position_id"], "position_id"):
                return f"❌ {err}"
            updates["position_id"] = args["position_id"]
        if args.get("status"):
            updates["status"] = args["status"]
        if args.get("phone"):
            updates["phone"] = args["phone"]
        if args.get("email"):
            updates["email"] = args["email"]

        if not updates:
            return "❌ 请提供至少一个要更新的字段"

        try:
            employee = await organization_service.update_employee(
                employee_id=employee_id,
                updates=updates,
                db=client,
            )

            return f"✅ 员工信息已更新: {employee.get('name')}"

        except Exception as e:
            logger.error(f"更新员工失败: {e}")
            return f"❌ 更新员工失败: {str(e)}"


class OrgStatisticsTool(BaseTool):
    """组织统计"""

    name = "org_statistics"
    description = "获取组织统计数据（总人数、部门分布、在职率等）。当用户说'组织统计'、'人员统计'、'有多少员工'时调用。"

    parameters = {
        "type": "object",
        "properties": {},
        "required": [],
    }

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        client = _get_client(config)
        org_id = _get_org_id(config)
        if not org_id:
            return "❌ 无法获取组织信息，请确保已正确登录。"

        try:
            stats = await organization_service.get_org_statistics(
                org_id=org_id,
                db=client,
            )

            return (
                f"📊 组织统计:\n\n"
                f"- 总员工数: {stats.get('total_employees')}\n"
                f"- 在职员工: {stats.get('active_employees')}\n"
                f"- 离职员工: {stats.get('resigned_employees')}\n"
                f"- 部门数: {stats.get('total_departments')}"
            )

        except Exception as e:
            logger.error(f"获取组织统计失败: {e}")
            return f"❌ 获取组织统计失败: {str(e)}"
