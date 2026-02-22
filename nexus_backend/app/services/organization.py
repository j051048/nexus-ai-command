"""
P2 Optimization: Organization Structure Management Service
Manages departments, teams, and organizational hierarchy.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from app.core.database import supabase
from app.services.cache_service import cache_service

logger = logging.getLogger(__name__)


@dataclass
class Department:
    """Represents a department in the organization"""

    id: str
    name: str
    parent_id: str | None = None
    manager_id: str | None = None
    budget_annual: float = 0.0
    employee_count: int = 0

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "parent_id": self.parent_id,
            "manager_id": self.manager_id,
            "budget_annual": self.budget_annual,
            "employee_count": self.employee_count,
        }


@dataclass
class OrgNode:
    """Node in the organization tree"""

    id: str
    name: str
    type: str  # 'department' or 'user'
    role: str | None = None
    parent_id: str | None = None
    children: list[OrgNode] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "role": self.role,
            "parent_id": self.parent_id,
            "children": [c.to_dict() for c in self.children],
            "metadata": self.metadata,
        }


class OrganizationService:
    """
    Service for managing organizational structure.
    Provides hierarchy traversal, reporting lines, and department management.
    """

    # Default departments for initialization
    DEFAULT_DEPARTMENTS = [
        {"id": "sales", "name": "销售部", "parent_id": None},
        {"id": "sales_domestic", "name": "国内销售组", "parent_id": "sales"},
        {"id": "sales_international", "name": "海外销售组", "parent_id": "sales"},
        {"id": "engineering", "name": "研发部", "parent_id": None},
        {"id": "product", "name": "产品部", "parent_id": None},
        {"id": "finance", "name": "财务部", "parent_id": None},
        {"id": "hr", "name": "人力资源部", "parent_id": None},
        {"id": "operations", "name": "运营部", "parent_id": None},
    ]

    async def get_all_departments(self) -> list[dict]:
        """
        Get all departments from database or return defaults.
        """
        if not supabase:
            return self.DEFAULT_DEPARTMENTS

        try:
            # Check cache first
            cached_deps = await cache_service.get("org:departments")
            if cached_deps:
                return cached_deps

            result = await supabase.table("departments").select("*").execute()
            departments = result.data or self.DEFAULT_DEPARTMENTS

            # Cache for 10 minutes
            await cache_service.set("org:departments", departments, ttl=600)

            return departments
        except Exception as e:
            logger.error(f"Error fetching departments: {e}")
            return self.DEFAULT_DEPARTMENTS

    async def get_department(self, department_id: str) -> dict | None:
        """
        Get a specific department by ID.
        """
        departments = await self.get_all_departments()
        return next((d for d in departments if d["id"] == department_id), None)

    async def get_department_tree(self) -> list[OrgNode]:
        """
        Build a hierarchical tree of departments.
        """
        departments = await self.get_all_departments()

        # Build lookup
        nodes: dict[str, OrgNode] = {}
        for dept in departments:
            nodes[dept["id"]] = OrgNode(
                id=dept["id"],
                name=dept["name"],
                type="department",
                parent_id=dept.get("parent_id"),
                metadata={
                    "manager_id": dept.get("manager_id"),
                    "budget": dept.get("budget_annual", 0),
                },
            )

        # Build hierarchy
        roots = []
        for node in nodes.values():
            if node.parent_id and node.parent_id in nodes:
                nodes[node.parent_id].children.append(node)
            else:
                roots.append(node)

        return roots

    async def get_department_members(self, department_id: str, db=None) -> list[dict]:
        """
        Get all members of a department.
        """
        client = db or supabase
        if not client:
            return []

        try:
            result = (
                await client.table("users")
                .select("id, name, role, score, rank")
                .eq("department", department_id)
                .execute()
            )

            return result.data or []
        except Exception as e:
            logger.error(f"Error fetching department members: {e}")
            return []

    async def get_user_reporting_line(self, user_id: str, db=None) -> list[dict]:
        """
        Get the reporting line (chain of managers) for a user.
        Returns list from immediate manager up to CEO.
        P2 Fix: Accept db parameter for RLS scoping.
        """
        client = db or supabase
        if not client:
            return []

        try:
            # P2 Fix: Batch fetch all users with manager_id to walk chain in memory
            all_users_res = (
                await client.table("users")
                .select("id, name, role, department, manager_id")
                .execute()
            )
            all_users = {u["id"]: u for u in (all_users_res.data or [])}

            reporting_line = []
            current_id = user_id
            visited = set()

            while current_id and current_id not in visited:
                visited.add(current_id)
                user_data = all_users.get(current_id)
                if not user_data:
                    break

                if current_id != user_id:
                    reporting_line.append({
                        "id": user_data["id"],
                        "name": user_data["name"],
                        "role": user_data["role"],
                        "department": user_data.get("department"),
                    })

                manager_id = user_data.get("manager_id")
                if not manager_id:
                    dept = user_data.get("department")
                    if dept:
                        dept_info = await self.get_department(dept)
                        manager_id = dept_info.get("manager_id") if dept_info else None

                current_id = manager_id

                if len(reporting_line) > 10:
                    break

            return reporting_line
        except Exception as e:
            logger.error(f"Error fetching reporting line: {e}")
            return []

    async def get_direct_reports(self, manager_id: str, db=None) -> list[dict]:
        """
        Get all users who directly report to a manager.
        """
        client = db or supabase
        if not client:
            return []

        try:
            result = (
                await client.table("users")
                .select("id, name, role, department, score")
                .eq("manager_id", manager_id)
                .execute()
            )

            return result.data or []
        except Exception as e:
            logger.error(f"Error fetching direct reports: {e}")
            return []

    async def get_team_hierarchy(self, manager_id: str, max_depth: int = 3, db=None) -> OrgNode:
        """
        Get the full team hierarchy under a manager.
        P2 Fix: Single query, build tree in memory instead of recursive N+1.
        """
        client = db or supabase
        if not client:
            return OrgNode(id=manager_id, name="Unknown", type="user")

        try:
            # Single query: fetch all users to build tree in memory
            all_res = (
                await client.table("users")
                .select("id, name, role, manager_id")
                .execute()
            )
            all_users = {u["id"]: u for u in (all_res.data or [])}

            def build_tree_in_memory(uid: str, depth: int) -> OrgNode | None:
                if depth > max_depth or uid not in all_users:
                    return None
                u = all_users[uid]
                node = OrgNode(id=u["id"], name=u["name"], type="user", role=u["role"])
                # Find direct reports from pre-fetched data
                for candidate in all_users.values():
                    if candidate.get("manager_id") == uid:
                        child = build_tree_in_memory(candidate["id"], depth + 1)
                        if child:
                            node.children.append(child)
                return node

            return build_tree_in_memory(manager_id, 0) or OrgNode(
                id=manager_id, name="Unknown", type="user"
            )
        except Exception as e:
            logger.error(f"Error building team hierarchy: {e}")
            return OrgNode(id=manager_id, name="Error", type="user")

    async def get_org_stats(self, org_id: str, db=None) -> dict[str, Any]:
        """
        Get overall organization statistics for a specific tenant.
        P2 Fix: Single query instead of 6 sequential queries (N+1 elimination).
        """
        client = db or supabase
        if not client:
            return {"error": "Database not connected"}

        try:
            # Single query: fetch all users with role and department
            result = (
                await client.table("users")
                .select("id, role, department")
                .eq("org_id", org_id)
                .execute()
            )
            users = result.data or []
            total_users = len(users)

            # Group by role in Python
            role_counts: dict[str, int] = {}
            dept_counts: dict[str, int] = {}
            for user in users:
                role = user.get("role") or "employee"
                role_counts[role] = role_counts.get(role, 0) + 1
                dept = user.get("department") or "未分配"
                dept_counts[dept] = dept_counts.get(dept, 0) + 1

            return {
                "total_employees": total_users,
                "by_role": role_counts,
                "by_department": dept_counts,
            }
        except Exception as e:
            logger.error(f"Error fetching org stats: {e}")
            return {"error": str(e)}

    async def update_user_department(
        self, user_id: str, new_department: str, new_manager_id: str | None = None
    ) -> bool:
        """
        Update a user's department and optionally their manager.
        """
        if not supabase:
            return False

        try:
            update_data = {"department": new_department}
            if new_manager_id:
                update_data["manager_id"] = new_manager_id

            await supabase.table("users").update(update_data).eq(
                "id", user_id
            ).execute()

            # Invalidate caches
            await cache_service.delete("org:departments")
            await cache_service.invalidate_user_cache(user_id)

            return True
        except Exception as e:
            logger.error(f"Error updating user department: {e}")
            return False


# Global service instance
organization_service = OrganizationService()
