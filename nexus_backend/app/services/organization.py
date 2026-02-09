"""
P2 Optimization: Organization Structure Management Service
Manages departments, teams, and organizational hierarchy.
"""
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from app.core.database import supabase
from app.services.cache_service import cache_service, cached


@dataclass
class Department:
    """Represents a department in the organization"""
    id: str
    name: str
    parent_id: Optional[str] = None
    manager_id: Optional[str] = None
    budget_annual: float = 0.0
    employee_count: int = 0
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "parent_id": self.parent_id,
            "manager_id": self.manager_id,
            "budget_annual": self.budget_annual,
            "employee_count": self.employee_count
        }


@dataclass
class OrgNode:
    """Node in the organization tree"""
    id: str
    name: str
    type: str  # 'department' or 'user'
    role: Optional[str] = None
    parent_id: Optional[str] = None
    children: List['OrgNode'] = None
    metadata: Dict = None
    
    def __post_init__(self):
        if self.children is None:
            self.children = []
        if self.metadata is None:
            self.metadata = {}
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "role": self.role,
            "parent_id": self.parent_id,
            "children": [c.to_dict() for c in self.children],
            "metadata": self.metadata
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
    
    async def get_all_departments(self) -> List[Dict]:
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
            print(f"Error fetching departments: {e}")
            return self.DEFAULT_DEPARTMENTS
    
    async def get_department(self, department_id: str) -> Optional[Dict]:
        """
        Get a specific department by ID.
        """
        departments = await self.get_all_departments()
        return next((d for d in departments if d["id"] == department_id), None)
    
    async def get_department_tree(self) -> List[OrgNode]:
        """
        Build a hierarchical tree of departments.
        """
        departments = await self.get_all_departments()
        
        # Build lookup
        nodes: Dict[str, OrgNode] = {}
        for dept in departments:
            nodes[dept["id"]] = OrgNode(
                id=dept["id"],
                name=dept["name"],
                type="department",
                parent_id=dept.get("parent_id"),
                metadata={
                    "manager_id": dept.get("manager_id"),
                    "budget": dept.get("budget_annual", 0)
                }
            )
        
        # Build hierarchy
        roots = []
        for node in nodes.values():
            if node.parent_id and node.parent_id in nodes:
                nodes[node.parent_id].children.append(node)
            else:
                roots.append(node)
        
        return roots
    
    async def get_department_members(self, department_id: str) -> List[Dict]:
        """
        Get all members of a department.
        """
        if not supabase:
            return []
        
        try:
            result = await supabase.table("users")\
                .select("id, name, role, score, rank")\
                .eq("department", department_id)\
                .execute()
            
            return result.data or []
        except Exception as e:
            print(f"Error fetching department members: {e}")
            return []
    
    async def get_user_reporting_line(self, user_id: str) -> List[Dict]:
        """
        Get the reporting line (chain of managers) for a user.
        Returns list from immediate manager up to CEO.
        """
        if not supabase:
            return []
        
        reporting_line = []
        current_id = user_id
        visited = set()
        
        try:
            while current_id and current_id not in visited:
                visited.add(current_id)
                
                # Get user info
                user = await supabase.table("users")\
                    .select("id, name, role, department, manager_id")\
                    .eq("id", current_id)\
                    .maybe_single()\
                    .execute()
                
                if not user.data:
                    break
                
                user_data = user.data
                
                # Skip the original user
                if current_id != user_id:
                    reporting_line.append({
                        "id": user_data["id"],
                        "name": user_data["name"],
                        "role": user_data["role"],
                        "department": user_data.get("department")
                    })
                
                # Get next manager
                manager_id = user_data.get("manager_id")
                if not manager_id:
                    # Try to find department manager
                    dept = user_data.get("department")
                    if dept:
                        dept_info = await self.get_department(dept)
                        manager_id = dept_info.get("manager_id") if dept_info else None
                
                current_id = manager_id
                
                # Safety limit
                if len(reporting_line) > 10:
                    break
            
            return reporting_line
        except Exception as e:
            print(f"Error fetching reporting line: {e}")
            return []
    
    async def get_direct_reports(self, manager_id: str) -> List[Dict]:
        """
        Get all users who directly report to a manager.
        """
        if not supabase:
            return []
        
        try:
            result = await supabase.table("users")\
                .select("id, name, role, department, score")\
                .eq("manager_id", manager_id)\
                .execute()
            
            return result.data or []
        except Exception as e:
            print(f"Error fetching direct reports: {e}")
            return []
    
    async def get_team_hierarchy(self, manager_id: str, max_depth: int = 3) -> OrgNode:
        """
        Get the full team hierarchy under a manager.
        """
        if not supabase:
            return OrgNode(id=manager_id, name="Unknown", type="user")
        
        async def build_tree(user_id: str, depth: int) -> OrgNode:
            if depth > max_depth:
                return None
            
            user = await supabase.table("users")\
                .select("id, name, role")\
                .eq("id", user_id)\
                .maybe_single()\
                .execute()
            
            if not user.data:
                return None
            
            node = OrgNode(
                id=user.data["id"],
                name=user.data["name"],
                type="user",
                role=user.data["role"]
            )
            
            # Get direct reports
            reports = await self.get_direct_reports(user_id)
            for report in reports:
                child = await build_tree(report["id"], depth + 1)
                if child:
                    node.children.append(child)
            
            return node
        
        try:
            return await build_tree(manager_id, 0)
        except Exception as e:
            print(f"Error building team hierarchy: {e}")
            return OrgNode(id=manager_id, name="Error", type="user")
    
    async def get_org_stats(self) -> Dict[str, Any]:
        """
        Get overall organization statistics.
        """
        if not supabase:
            return {"error": "Database not connected"}
        
        try:
            # Total employees
            users = await supabase.table("users")\
                .select("id", count="exact")\
                .execute()
            total_users = users.count or 0
            
            # By role
            role_counts = {}
            for role in ["founder", "manager", "sales", "employee"]:
                count = await supabase.table("users")\
                    .select("id", count="exact")\
                    .eq("role", role)\
                    .execute()
                role_counts[role] = count.count or 0
            
            # By department
            dept_data = await supabase.table("users")\
                .select("department")\
                .execute()
            
            dept_counts = {}
            for user in dept_data.data or []:
                dept = user.get("department") or "未分配"
                dept_counts[dept] = dept_counts.get(dept, 0) + 1
            
            return {
                "total_employees": total_users,
                "by_role": role_counts,
                "by_department": dept_counts,
                "departments_count": len(await self.get_all_departments())
            }
        except Exception as e:
            print(f"Error fetching org stats: {e}")
            return {"error": str(e)}
    
    async def update_user_department(
        self, 
        user_id: str, 
        new_department: str,
        new_manager_id: Optional[str] = None
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
            
            await supabase.table("users")\
                .update(update_data)\
                .eq("id", user_id)\
                .execute()
            
            # Invalidate caches
            await cache_service.delete("org:departments")
            await cache_service.invalidate_user_cache(user_id)
            
            return True
        except Exception as e:
            print(f"Error updating user department: {e}")
            return False


# Global service instance
organization_service = OrganizationService()