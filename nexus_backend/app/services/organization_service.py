"""
组织架构服务
提供部门、职位、员工管理功能
"""

import logging

from app.core.cache import cache, invalidate_cache

logger = logging.getLogger(__name__)


class OrgNode:
    """组织架构节点，用于构建树形结构"""

    def __init__(
        self,
        id,
        name,
        parent_id=None,
        type="department",
        manager_id=None,
        manager_name=None,
    ):
        self.id = id
        self.name = name
        self.parent_id = parent_id
        self.type = type
        self.manager_id = manager_id
        self.manager_name = manager_name
        self.children = []
        self.members = []

    def add_child(self, node):
        self.children.append(node)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "parent_id": self.parent_id,
            "type": self.type,
            "manager_id": self.manager_id,
            "manager_name": self.manager_name,
            "children": [child.to_dict() for child in self.children],
            "members": self.members,
        }


class OrganizationService:
    """组织架构管理服务"""

    # ========================================================================
    # 组织基础信息
    # ========================================================================

    async def get_organization(self, org_id: str, db=None) -> dict | None:
        """获取组织基础信息"""
        if not db:
            raise RuntimeError("数据库连接不可用")
        try:
            result = (
                await db.table("organizations")
                .select("*")
                .eq("id", org_id)
                .maybe_single()
                .execute()
            )
            return result.data
        except Exception as e:
            logger.error(f"获取组织信息失败: {e}")
            raise

    async def update_organization(self, org_id: str, updates: dict, db=None) -> dict:
        """更新组织信息"""
        if not db:
            raise RuntimeError("数据库连接不可用")
        try:
            result = (
                await db.table("organizations")
                .update(updates)
                .eq("id", org_id)
                .execute()
            )
            if result.data and len(result.data) > 0:
                logger.info(f"组织已更新: id={org_id}")
                invalidate_cache(f"org:cache:*get_organization*{org_id}*")
                return result.data[0]
            raise RuntimeError("组织更新失败")
        except Exception as e:
            logger.error(f"更新组织信息失败: {e}")
            raise

    async def get_org_stats(self, org_id: str, db=None) -> dict:
        """获取组织统计概览"""
        return await self.get_org_statistics(org_id, db=db)

    async def get_org_statistics(self, org_id: str, db=None) -> dict:
        """获取组织统计数据"""
        if not db:
            return {
                "member_count": 0,
                "department_count": 0,
                "role_count": 0,
                "active_employees": 0,
            }
        try:
            # 1. 统计员工总数
            members = (
                await db.table("users")
                .select("id", count="exact")
                .eq("organization_id", org_id)
                .execute()
            )
            member_count = members.count or 0

            # 2. 统计部门数
            depts = (
                await db.table("departments")
                .select("id", count="exact")
                .eq("organization_id", org_id)
                .execute()
            )
            dept_count = depts.count or 0

            # 3. 统计常见职位数 (基于 role 类型去重统计)
            roles = (
                await db.table("users")
                .select("role")
                .eq("organization_id", org_id)
                .execute()
            )
            unique_roles = set(r["role"] for r in (roles.data or []) if r.get("role"))
            role_count = len(unique_roles)

            return {
                "member_count": member_count,
                "total_employees": member_count,
                "active_employees": member_count,  # 默认全活跃
                "department_count": dept_count,
                "total_departments": dept_count,
                "role_count": role_count,
            }
        except Exception as e:
            logger.error(f"获取组织统计失败: {e}")
            return {"error": str(e)}

    # ========================================================================
    # 部门管理
    # ========================================================================

    async def get_all_departments(self, db=None) -> list[dict]:
        """获取所有部门列表 (RLS 处理过滤)"""
        if not db:
            raise RuntimeError("数据库连接不可用")
        try:
            result = (
                await db.table("departments")
                .select("*")
                .eq("status", "active")
                .order("sort_order")
                .execute()
            )
            return result.data or []
        except Exception as e:
            logger.error(f"获取所有部门失败: {e}")
            raise

    async def get_department(self, department_id: str, db=None) -> dict | None:
        """获取部门详情"""
        if not db:
            raise RuntimeError("数据库连接不可用")
        try:
            result = (
                await db.table("departments")
                .select("*")
                .eq("id", department_id)
                .maybe_single()
                .execute()
            )
            return result.data
        except Exception as e:
            logger.error(f"获取部门详情失败: {e}")
            raise

    async def get_department_members(self, department_id: str, db=None) -> list[dict]:
        """获取部门下所有成员"""
        if not db:
            raise RuntimeError("数据库连接不可用")
        try:
            # 优先查 employees，兜底查 users
            employees = (
                await db.table("employees")
                .select("*")
                .eq("department_id", department_id)
                .execute()
            )
            if employees.data:
                return employees.data

            # 尝试根据名称匹配 (部分版本 users 表存的是 department 名称)
            dept = await self.get_department(department_id, db=db)
            if dept:
                users = (
                    await db.table("users")
                    .select("*")
                    .eq("department", dept["name"])
                    .execute()
                )
                return users.data or []
            return []
        except Exception as e:
            logger.error(f"获取部门成员失败: {e}")
            return []

    async def get_department_tree(self, db=None) -> list[OrgNode]:
        """构建完整的部门树结构"""
        departments = await self.get_all_departments(db=db)
        if not departments:
            return []

        nodes = {
            d["id"]: OrgNode(
                d["id"], d["name"], d.get("parent_id"), manager_id=d.get("manager_id")
            )
            for d in departments
        }
        tree = []

        for d in departments:
            node = nodes[d["id"]]
            parent_id = d.get("parent_id")
            if parent_id and parent_id in nodes:
                nodes[parent_id].add_child(node)
            else:
                tree.append(node)

        return tree

    @cache(ttl=300, prefix="org")
    async def list_departments(
        self,
        org_id: str,
        parent_id: str | None = None,
        db=None,
    ) -> list[dict]:
        """查询部门列表"""
        if not db:
            raise RuntimeError("数据库连接不可用")
        try:
            query = (
                db.table("departments")
                .select("*")
                .eq("organization_id", org_id)
                .eq("status", "active")
                .order("sort_order", desc=False)
            )
            if parent_id is not None:
                query = (
                    query.is_("parent_id", "null")
                    if parent_id == "root"
                    else query.eq("parent_id", parent_id)
                )
            result = await query.execute()
            return result.data or []
        except Exception as e:
            logger.error(f"查询部门列表失败: {e}")
            raise

    async def create_department(
        self,
        org_id: str,
        name: str,
        parent_id: str | None = None,
        manager_id: str | None = None,
        sort_order: int = 0,
        db=None,
    ) -> dict:
        """创建部门"""
        if not db:
            raise RuntimeError("数据库连接不可用")
        try:
            data = {
                "organization_id": org_id,
                "name": name,
                "parent_id": parent_id,
                "manager_id": manager_id,
                "sort_order": sort_order,
                "status": "active",
            }
            result = await db.table("departments").insert(data).execute()
            if result.data:
                invalidate_cache(f"org:cache:*list_departments*{org_id}*")
                return result.data[0]
            raise RuntimeError("创建失败")
        except Exception as e:
            logger.error(f"创建部门失败: {e}")
            raise

    async def update_department(
        self, department_id: str, updates: dict, db=None
    ) -> dict:
        """更新部门"""
        if not db:
            raise RuntimeError("数据库连接不可用")
        try:
            result = (
                await db.table("departments")
                .update(updates)
                .eq("id", department_id)
                .execute()
            )
            if result.data:
                org_id = result.data[0].get("organization_id")
                invalidate_cache(f"org:cache:*list_departments*{org_id}*")
                return result.data[0]
            raise RuntimeError("更新失败")
        except Exception as e:
            logger.error(f"更新部门失败: {e}")
            raise

    async def delete_department(self, department_id: str, db=None) -> dict:
        """软删除部门"""
        return await self.update_department(
            department_id, {"status": "dissolved"}, db=db
        )

    # ========================================================================
    # 汇报线与层级
    # ========================================================================

    async def get_user_reporting_line(self, user_id: str, db=None) -> list[dict]:
        """获取员工的汇报线 (向上追踪)"""
        if not db:
            return []
        try:
            line = []
            curr_id = user_id
            visited = set()
            while curr_id and curr_id not in visited:
                visited.add(curr_id)
                user = (
                    await db.table("users")
                    .select("id, name, role, manager_id, avatar")
                    .eq("id", curr_id)
                    .maybe_single()
                    .execute()
                )
                if not user.data:
                    break
                line.append(user.data)
                curr_id = user.data.get("manager_id")
            return line
        except Exception as e:
            logger.error(f"获取汇报线失败: {e}")
            return []

    async def get_direct_reports(self, manager_id: str, db=None) -> list[dict]:
        """获取直属下级"""
        if not db:
            return []
        try:
            result = (
                await db.table("users")
                .select("id, name, role, department, avatar")
                .eq("manager_id", manager_id)
                .execute()
            )
            return result.data or []
        except Exception as e:
            logger.error(f"获取直属下级失败: {e}")
            return []

    async def get_team_hierarchy(self, manager_id: str, db=None) -> dict:
        """构建团队层级结构 (向下追踪)"""
        manager = (
            await db.table("users")
            .select("id, name, role, department, avatar")
            .eq("id", manager_id)
            .maybe_single()
            .execute()
        )
        if not manager.data:
            return {}

        root = {**manager.data, "children": []}

        # 简单递归获取 2 层
        direct_reports = await self.get_direct_reports(manager_id, db=db)
        for report in direct_reports:
            report_node = {**report, "children": []}
            # 获取孙子辈
            grand_reports = await self.get_direct_reports(report["id"], db=db)
            report_node["children"] = grand_reports
            root["children"].append(report_node)

        return root

    # ========================================================================
    # 职位与员工 (保持原有逻辑)
    # ========================================================================

    async def list_positions(
        self, org_id: str, department_id: str | None = None, db=None
    ) -> list[dict]:
        if not db:
            return []
        query = db.table("positions").select("*").eq("organization_id", org_id)
        if department_id:
            query = query.eq("department_id", department_id)
        res = await query.execute()
        return res.data or []

    async def list_employees(
        self, org_id: str, filters: dict | None = None, db=None
    ) -> list[dict]:
        # 简化版实现，保留核心
        if not db:
            return []
        query = db.table("users").select("*").eq("organization_id", org_id)
        if filters and filters.get("search"):
            query = query.or_(
                f"name.ilike.%{filters['search']}%,role.ilike.%{filters['search']}%"
            )
        res = await query.execute()
        return res.data or []

    async def get_employee_detail(self, employee_id: str, db=None) -> dict | None:
        if not db:
            return None
        res = (
            await db.table("users")
            .select("*")
            .eq("id", employee_id)
            .maybe_single()
            .execute()
        )
        return res.data

    async def update_employee(self, employee_id: str, updates: dict, db=None) -> dict:
        if not db:
            raise RuntimeError("N/A")
        res = await db.table("users").update(updates).eq("id", employee_id).execute()
        return res.data[0] if res.data else {}


organization_service = OrganizationService()
