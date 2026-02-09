
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from app.core.database import supabase
from app.services.cache_service import cache_service

logger = logging.getLogger(__name__)

@dataclass
class Department:
    """Represents a department in the organization"""
    id: str
# ... (rest of the file until the print statements)

class OrganizationService:
    # ...
    
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
            logger.error(f"Error fetching departments: {e}")
            return self.DEFAULT_DEPARTMENTS
    
    # ...

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
            logger.error(f"Error fetching department members: {e}")
            return []
    
    async def get_user_reporting_line(self, user_id: str) -> List[Dict]:
        # ...
        try:
            # ...
            return reporting_line
        except Exception as e:
            logger.error(f"Error fetching reporting line: {e}")
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
            logger.error(f"Error fetching direct reports: {e}")
            return []
    
    async def get_team_hierarchy(self, manager_id: str, max_depth: int = 3) -> OrgNode:
        # ...
        try:
            return await build_tree(manager_id, 0)
        except Exception as e:
            logger.error(f"Error building team hierarchy: {e}")
            return OrgNode(id=manager_id, name="Error", type="user")
    
    async def get_org_stats(self) -> Dict[str, Any]:
        # ...
        try:
            # ...
            return {
                "total_employees": total_users,
                "by_role": role_counts,
                "by_department": dept_counts,
                "departments_count": len(await self.get_all_departments())
            }
        except Exception as e:
            logger.error(f"Error fetching org stats: {e}")
            return {"error": str(e)}
    
    async def update_user_department(
        self, 
        user_id: str, 
        new_department: str,
        new_manager_id: Optional[str] = None
    ) -> bool:
        # ...
        try:
            # ...
            return True
        except Exception as e:
            logger.error(f"Error updating user department: {e}")
            return False


# Global service instance
organization_service = OrganizationService()