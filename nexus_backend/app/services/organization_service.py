"""
组织架构服务
提供部门、职位、员工管理功能
"""

import logging

logger = logging.getLogger(__name__)


class OrganizationService:
    """组织架构管理服务"""

    # ========================================================================
    # 部门管理
    # ========================================================================

    async def list_departments(
        self,
        org_id: str,
        parent_id: str | None = None,
        db=None,
    ) -> list[dict]:
        """
        查询部门列表

        Args:
            org_id: 组织ID
            parent_id: 父部门ID（可选，查询子部门）
            db: 数据库客户端

        Returns:
            部门列表
        """
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

            if parent_id:
                query = query.eq("parent_id", parent_id)
            elif parent_id is None:
                # 查询顶级部门
                query = query.is_("parent_id", "null")

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
        """
        创建部门

        Args:
            org_id: 组织ID
            name: 部门名称
            parent_id: 父部门ID
            manager_id: 部门负责人ID
            sort_order: 排序
            db: 数据库客户端

        Returns:
            部门对象
        """
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

            if result.data and len(result.data) > 0:
                logger.info(f"部门已创建: org={org_id}, name={name}")
                return result.data[0]

            raise RuntimeError("部门创建失败")

        except Exception as e:
            logger.error(f"创建部门失败: {e}")
            raise

    async def update_department(
        self,
        department_id: str,
        updates: dict,
        db=None,
    ) -> dict:
        """
        更新部门信息

        Args:
            department_id: 部门ID
            updates: 更新字段
            db: 数据库客户端

        Returns:
            更新后的部门对象
        """
        if not db:
            raise RuntimeError("数据库连接不可用")

        try:
            result = await db.table("departments").update(updates).eq("id", department_id).execute()

            if result.data and len(result.data) > 0:
                logger.info(f"部门已更新: id={department_id}")
                return result.data[0]

            raise RuntimeError("部门更新失败")

        except Exception as e:
            logger.error(f"更新部门失败: {e}")
            raise

    # ========================================================================
    # 职位管理
    # ========================================================================

    async def list_positions(
        self,
        org_id: str,
        department_id: str | None = None,
        db=None,
    ) -> list[dict]:
        """
        查询职位列表

        Args:
            org_id: 组织ID
            department_id: 部门ID（可选）
            db: 数据库客户端

        Returns:
            职位列表
        """
        if not db:
            raise RuntimeError("数据库连接不可用")

        try:
            query = db.table("positions").select("*").eq("organization_id", org_id).order("level", desc=False)

            if department_id:
                query = query.eq("department_id", department_id)

            result = await query.execute()
            return result.data or []

        except Exception as e:
            logger.error(f"查询职位列表失败: {e}")
            raise

    async def create_position(
        self,
        org_id: str,
        name: str,
        level: int = 1,
        department_id: str | None = None,
        db=None,
    ) -> dict:
        """
        创建职位

        Args:
            org_id: 组织ID
            name: 职位名称
            level: 职级
            department_id: 部门ID
            db: 数据库客户端

        Returns:
            职位对象
        """
        if not db:
            raise RuntimeError("数据库连接不可用")

        try:
            data = {
                "organization_id": org_id,
                "name": name,
                "level": level,
                "department_id": department_id,
            }

            result = await db.table("positions").insert(data).execute()

            if result.data and len(result.data) > 0:
                logger.info(f"职位已创建: org={org_id}, name={name}")
                return result.data[0]

            raise RuntimeError("职位创建失败")

        except Exception as e:
            logger.error(f"创建职位失败: {e}")
            raise

    # ========================================================================
    # 员工管理
    # ========================================================================

    async def list_employees(
        self,
        org_id: str,
        filters: dict | None = None,
        db=None,
    ) -> list[dict]:
        """
        查询员工列表

        Args:
            org_id: 组织ID
            filters: 筛选条件 {department_id, position_id, status, search}
            db: 数据库客户端

        Returns:
            员工列表
        """
        if not db:
            raise RuntimeError("数据库连接不可用")

        try:
            query = (
                db.table("employees")
                .select("*, position:positions(id, name, level)")
                .eq("organization_id", org_id)
                .order("created_at", desc=True)
            )

            if filters:
                if filters.get("department_id"):
                    query = query.eq("department_id", filters["department_id"])
                if filters.get("position_id"):
                    query = query.eq("position_id", filters["position_id"])
                if filters.get("status"):
                    query = query.eq("status", filters["status"])
                if filters.get("search"):
                    search = filters["search"]
                    query = query.or_(f"name.ilike.%{search}%,phone.ilike.%{search}%,email.ilike.%{search}%")

            result = await query.execute()
            return result.data or []

        except Exception as e:
            logger.error(f"查询员工列表失败: {e}")
            raise

    async def get_employee_detail(
        self,
        employee_id: str,
        db=None,
    ) -> dict | None:
        """
        获取员工详情

        Args:
            employee_id: 员工ID
            db: 数据库客户端

        Returns:
            员工详情
        """
        if not db:
            raise RuntimeError("数据库连接不可用")

        try:
            result = await (
                db.table("employees")
                .select("*, position:positions(id, name, level)")
                .eq("id", employee_id)
                .maybe_single()
                .execute()
            )

            return result.data

        except Exception as e:
            logger.error(f"获取员工详情失败: {e}")
            raise

    async def create_employee(
        self,
        org_id: str,
        data: dict,
        db=None,
    ) -> dict:
        """
        创建员工

        Args:
            org_id: 组织ID
            data: 员工数据
            db: 数据库客户端

        Returns:
            员工对象
        """
        if not db:
            raise RuntimeError("数据库连接不可用")

        try:
            data["organization_id"] = org_id
            data.setdefault("status", "active")

            result = await db.table("employees").insert(data).execute()

            if result.data and len(result.data) > 0:
                logger.info(f"员工已创建: org={org_id}, name={data.get('name')}")
                return result.data[0]

            raise RuntimeError("员工创建失败")

        except Exception as e:
            logger.error(f"创建员工失败: {e}")
            raise

    async def update_employee(
        self,
        employee_id: str,
        updates: dict,
        db=None,
    ) -> dict:
        """
        更新员工信息

        Args:
            employee_id: 员工ID
            updates: 更新字段
            db: 数据库客户端

        Returns:
            更新后的员工对象
        """
        if not db:
            raise RuntimeError("数据库连接不可用")

        try:
            result = await db.table("employees").update(updates).eq("id", employee_id).execute()

            if result.data and len(result.data) > 0:
                logger.info(f"员工已更新: id={employee_id}")
                return result.data[0]

            raise RuntimeError("员工更新失败")

        except Exception as e:
            logger.error(f"更新员工失败: {e}")
            raise

    async def get_org_statistics(
        self,
        org_id: str,
        db=None,
    ) -> dict:
        """
        获取组织统计数据

        Args:
            org_id: 组织ID
            db: 数据库客户端

        Returns:
            统计数据
        """
        if not db:
            raise RuntimeError("数据库连接不可用")

        try:
            # 总人数
            total_result = await (
                db.table("employees").select("id", count="exact").eq("organization_id", org_id).execute()
            )
            total_count = total_result.count or 0

            # 在职人数
            active_result = await (
                db.table("employees")
                .select("id", count="exact")
                .eq("organization_id", org_id)
                .eq("status", "active")
                .execute()
            )
            active_count = active_result.count or 0

            # 部门数
            dept_result = await (
                db.table("departments")
                .select("id", count="exact")
                .eq("organization_id", org_id)
                .eq("status", "active")
                .execute()
            )
            dept_count = dept_result.count or 0

            return {
                "total_employees": total_count,
                "active_employees": active_count,
                "resigned_employees": total_count - active_count,
                "total_departments": dept_count,
            }

        except Exception as e:
            logger.error(f"获取组织统计失败: {e}")
            raise


organization_service = OrganizationService()
