"""
Item 7: ABAC Permission Service
基于属性的访问控制 (Attribute-Based Access Control) 服务。
从简单的 role 字段升级为更细粒度的权限评估体系。

支持:
- 基于角色的权限规则
- 基于条件的动态权限（如 is_owner, same_department, is_approver）
- 用户权限列表查询
- 权限缓存（减少数据库查询）
"""

import logging
import time
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
from app.core.database import supabase

logger = logging.getLogger(__name__)


# ============== 数据模型 ==============


@dataclass
class PermissionRule:
    """权限规则定义"""
    permission: str
    roles: List[str]
    conditions: List[str] = field(default_factory=list)
    description: str = ""


@dataclass
class PermissionContext:
    """权限评估上下文"""
    user_id: str
    user_role: Optional[str] = None
    user_department: Optional[str] = None
    org_id: Optional[str] = None
    resource: Optional[Dict[str, Any]] = None


@dataclass
class PermissionResult:
    """权限评估结果"""
    granted: bool
    permission: str
    reason: str = ""
    evaluated_conditions: List[Dict[str, Any]] = field(default_factory=list)


# ============== 权限缓存 ==============


class PermissionCache:
    """简单的内存缓存，用于减少权限查询的数据库访问"""

    def __init__(self, ttl_seconds: int = 300):
        self._cache: Dict[str, Any] = {}
        self._timestamps: Dict[str, float] = {}
        self._ttl = ttl_seconds
        self._max_entries = 500

    def get(self, key: str) -> Optional[Any]:
        """获取缓存值，如果过期则返回 None"""
        if key not in self._cache:
            return None
        if time.time() - self._timestamps.get(key, 0) > self._ttl:
            del self._cache[key]
            del self._timestamps[key]
            return None
        return self._cache[key]

    def set(self, key: str, value: Any) -> None:
        """设置缓存值"""
        if len(self._cache) >= self._max_entries:
            # 淘汰最旧的条目
            oldest_key = min(self._timestamps, key=self._timestamps.get)
            del self._cache[oldest_key]
            del self._timestamps[oldest_key]
        self._cache[key] = value
        self._timestamps[key] = time.time()

    def invalidate(self, key: str) -> None:
        """使缓存失效"""
        self._cache.pop(key, None)
        self._timestamps.pop(key, None)

    def invalidate_user(self, user_id: str) -> None:
        """使某个用户的所有缓存失效"""
        keys_to_remove = [k for k in self._cache if k.startswith(f"user:{user_id}:")]
        for key in keys_to_remove:
            self.invalidate(key)

    def clear(self) -> None:
        """清空所有缓存"""
        self._cache.clear()
        self._timestamps.clear()


# ============== 权限服务 ==============


class PermissionService:
    """
    ABAC 权限评估服务。

    权限规则由 PERMISSION_RULES 静态定义，同时支持条件动态评估。
    角色层级: founder > boss > manager > employee

    条件说明:
    - is_owner: 用户是资源的创建者/所有者
    - same_department: 用户与目标资源属于同一部门
    - is_approver: 用户是审批链中的审批人
    - is_self: 用户操作的是自身资源
    """

    # 角色层级（高到低）
    ROLE_HIERARCHY = {
        "founder": 4,
        "boss": 3,
        "manager": 2,
        "employee": 1,
        "guest": 0,
    }

    # 权限规则定义
    PERMISSION_RULES: Dict[str, Dict[str, Any]] = {
        # 审批相关
        "approval.create": {
            "roles": ["employee", "manager", "boss", "founder"],
            "conditions": [],
            "description": "创建审批请求",
        },
        "approval.view": {
            "roles": ["employee", "manager", "boss", "founder"],
            "conditions": [],
            "description": "查看审批请求",
        },
        "approval.approve": {
            "roles": ["manager", "boss", "founder"],
            "conditions": ["is_approver"],
            "description": "审批通过/驳回",
        },
        "approval.delete": {
            "roles": ["founder"],
            "conditions": [],
            "description": "删除审批记录",
        },
        "approval.export": {
            "roles": ["manager", "boss", "founder"],
            "conditions": [],
            "description": "导出审批数据",
        },
        # 工作流管理
        "workflow.view": {
            "roles": ["manager", "boss", "founder"],
            "conditions": [],
            "description": "查看工作流",
        },
        "workflow.manage": {
            "roles": ["boss", "founder"],
            "conditions": [],
            "description": "管理工作流",
        },
        # 表单模板
        "form_schema.view": {
            "roles": ["employee", "manager", "boss", "founder"],
            "conditions": [],
            "description": "查看表单模板",
        },
        "form_schema.manage": {
            "roles": ["boss", "founder"],
            "conditions": [],
            "description": "管理表单模板",
        },
        # 用户管理
        "user.manage": {
            "roles": ["founder"],
            "conditions": [],
            "description": "管理用户（增删改）",
        },
        "user.view": {
            "roles": ["manager", "boss", "founder"],
            "conditions": ["same_department"],
            "description": "查看用户信息",
        },
        "user.view_self": {
            "roles": ["employee", "manager", "boss", "founder"],
            "conditions": [],
            "description": "查看自身信息",
        },
        # 报表
        "report.view": {
            "roles": ["manager", "boss", "founder"],
            "conditions": [],
            "description": "查看报表",
        },
        "report.export": {
            "roles": ["boss", "founder"],
            "conditions": [],
            "description": "导出报表",
        },
        # 系统设置
        "settings.view": {
            "roles": ["boss", "founder"],
            "conditions": [],
            "description": "查看系统设置",
        },
        "settings.manage": {
            "roles": ["founder"],
            "conditions": [],
            "description": "修改系统设置",
        },
        # 文档/知识库
        "document.view": {
            "roles": ["employee", "manager", "boss", "founder"],
            "conditions": [],
            "description": "查看文档",
        },
        "document.upload": {
            "roles": ["employee", "manager", "boss", "founder"],
            "conditions": [],
            "description": "上传文档",
        },
        "document.delete": {
            "roles": ["boss", "founder"],
            "conditions": ["is_owner"],
            "description": "删除文档",
        },
        # 审计日志
        "audit.view": {
            "roles": ["boss", "founder"],
            "conditions": [],
            "description": "查看审计日志",
        },
        # 数据导入/导出
        "data.import": {
            "roles": ["manager", "boss", "founder"],
            "conditions": [],
            "description": "批量导入数据",
        },
        "data.export": {
            "roles": ["manager", "boss", "founder"],
            "conditions": [],
            "description": "批量导出数据",
        },
        # IM 集成
        "im.view": {
            "roles": ["boss", "founder"],
            "conditions": [],
            "description": "查看 IM 集成配置",
        },
        "im.manage": {
            "roles": ["founder"],
            "conditions": [],
            "description": "管理 IM 集成",
        },
        # 销售管理
        "sales.view": {
            "roles": ["employee", "manager", "boss", "founder"],
            "conditions": [],
            "description": "查看销售数据",
        },
        "sales.manage": {
            "roles": ["manager", "boss", "founder"],
            "conditions": [],
            "description": "管理销售数据",
        },
        # 项目管理
        "project.view": {
            "roles": ["employee", "manager", "boss", "founder"],
            "conditions": [],
            "description": "查看项目",
        },
        "project.manage": {
            "roles": ["manager", "boss", "founder"],
            "conditions": [],
            "description": "管理项目",
        },
        # 激励/钱包
        "incentive.view": {
            "roles": ["employee", "manager", "boss", "founder"],
            "conditions": [],
            "description": "查看激励钱包",
        },
        "incentive.manage": {
            "roles": ["boss", "founder"],
            "conditions": [],
            "description": "管理激励发放",
        },
        # 订阅/计费
        "billing.view": {
            "roles": ["boss", "founder"],
            "conditions": [],
            "description": "查看计费信息",
        },
        "billing.manage": {
            "roles": ["founder"],
            "conditions": [],
            "description": "管理订阅计划",
        },
    }

    def __init__(self):
        self._cache = PermissionCache(ttl_seconds=300)

    # ============== 核心权限检查 ==============

    async def check_permission(
        self,
        user_id: str,
        permission: str,
        resource: Optional[Dict[str, Any]] = None,
        db=None,
    ) -> bool:
        """
        检查用户是否有指定权限。

        Args:
            user_id: 用户 ID
            permission: 权限标识（如 'approval.create'）
            resource: 可选的资源上下文（用于条件评估）
            db: 数据库客户端

        Returns:
            True 如果用户有权限，否则 False
        """
        db = db or supabase
        if not db:
            logger.warning("No database connection for permission check")
            return False

        # 查找权限规则
        rule = self.PERMISSION_RULES.get(permission)
        if not rule:
            logger.warning(f"Unknown permission: {permission}")
            return False

        try:
            # 获取用户角色（带缓存）
            user_info = await self._get_user_info(user_id, db)
            if not user_info:
                logger.warning(f"User not found for permission check: {user_id}")
                return False

            user_role = user_info.get("role", "employee")

            # 1. 检查角色是否在允许列表中
            if user_role not in rule["roles"]:
                # 检查角色层级 - 更高级别的角色自动拥有低级别权限
                if not self._role_has_hierarchy_access(user_role, rule["roles"]):
                    return False

            # 2. 如果有条件约束，评估条件
            conditions = rule.get("conditions", [])
            if conditions and resource:
                # 条件采用 OR 逻辑：满足任一条件即可
                condition_met = False
                for condition in conditions:
                    if await self._evaluate_condition(
                        condition, user_id, user_info, resource, db
                    ):
                        condition_met = True
                        break

                if not condition_met:
                    return False

            return True

        except Exception as e:
            logger.error(f"Permission check error: {e}")
            return False

    async def check_permission_detailed(
        self,
        user_id: str,
        permission: str,
        resource: Optional[Dict[str, Any]] = None,
        db=None,
    ) -> PermissionResult:
        """
        详细的权限检查，返回评估过程信息。

        Args:
            user_id: 用户 ID
            permission: 权限标识
            resource: 可选的资源上下文
            db: 数据库客户端

        Returns:
            PermissionResult 包含详细评估信息
        """
        db = db or supabase
        if not db:
            return PermissionResult(
                granted=False,
                permission=permission,
                reason="数据库连接不可用",
            )

        rule = self.PERMISSION_RULES.get(permission)
        if not rule:
            return PermissionResult(
                granted=False,
                permission=permission,
                reason=f"未知权限: {permission}",
            )

        try:
            user_info = await self._get_user_info(user_id, db)
            if not user_info:
                return PermissionResult(
                    granted=False,
                    permission=permission,
                    reason="用户不存在",
                )

            user_role = user_info.get("role", "employee")
            evaluated_conditions = []

            # 检查角色
            role_allowed = user_role in rule["roles"] or self._role_has_hierarchy_access(
                user_role, rule["roles"]
            )
            if not role_allowed:
                return PermissionResult(
                    granted=False,
                    permission=permission,
                    reason=f"角色 {user_role} 不在允许列表 {rule['roles']} 中",
                )

            # 检查条件
            conditions = rule.get("conditions", [])
            if conditions and resource:
                for condition in conditions:
                    result = await self._evaluate_condition(
                        condition, user_id, user_info, resource, db
                    )
                    evaluated_conditions.append({
                        "condition": condition,
                        "result": result,
                    })

                if not any(ec["result"] for ec in evaluated_conditions):
                    return PermissionResult(
                        granted=False,
                        permission=permission,
                        reason="条件约束未满足",
                        evaluated_conditions=evaluated_conditions,
                    )

            return PermissionResult(
                granted=True,
                permission=permission,
                reason="权限通过",
                evaluated_conditions=evaluated_conditions,
            )

        except Exception as e:
            logger.error(f"Detailed permission check error: {e}")
            return PermissionResult(
                granted=False,
                permission=permission,
                reason=f"评估异常: {str(e)}",
            )

    async def get_user_permissions(
        self, user_id: str, db=None
    ) -> List[Dict[str, Any]]:
        """
        获取用户所有权限列表。

        Args:
            user_id: 用户 ID
            db: 数据库客户端

        Returns:
            权限列表，每项包含 permission, granted, description
        """
        db = db or supabase
        if not db:
            return []

        try:
            user_info = await self._get_user_info(user_id, db)
            if not user_info:
                return []

            user_role = user_info.get("role", "employee")
            permissions = []

            for perm_key, rule in self.PERMISSION_RULES.items():
                granted = user_role in rule["roles"] or self._role_has_hierarchy_access(
                    user_role, rule["roles"]
                )
                has_conditions = bool(rule.get("conditions"))

                permissions.append({
                    "permission": perm_key,
                    "granted": granted,
                    "conditional": has_conditions,
                    "description": rule.get("description", ""),
                    "required_roles": rule["roles"],
                    "conditions": rule.get("conditions", []),
                })

            return permissions

        except Exception as e:
            logger.error(f"Get user permissions error: {e}")
            return []

    def get_all_permissions(self) -> List[Dict[str, Any]]:
        """
        获取所有权限规则定义（不依赖数据库）。

        Returns:
            所有权限规则列表
        """
        return [
            {
                "permission": perm_key,
                "roles": rule["roles"],
                "conditions": rule.get("conditions", []),
                "description": rule.get("description", ""),
            }
            for perm_key, rule in self.PERMISSION_RULES.items()
        ]

    def get_role_permissions(self, role: str) -> List[str]:
        """
        获取指定角色拥有的所有权限标识。

        Args:
            role: 角色名

        Returns:
            权限标识列表
        """
        permissions = []
        for perm_key, rule in self.PERMISSION_RULES.items():
            if role in rule["roles"] or self._role_has_hierarchy_access(
                role, rule["roles"]
            ):
                permissions.append(perm_key)
        return permissions

    # ============== 条件评估 ==============

    async def _evaluate_condition(
        self,
        condition: str,
        user_id: str,
        user_info: Dict[str, Any],
        resource: Dict[str, Any],
        db,
    ) -> bool:
        """
        评估单个条件。

        Args:
            condition: 条件名称
            user_id: 用户 ID
            user_info: 用户信息字典
            resource: 资源上下文
            db: 数据库客户端

        Returns:
            True 如果条件满足
        """
        try:
            if condition == "is_owner":
                return await self._check_is_owner(user_id, resource, db)
            elif condition == "same_department":
                return await self._check_same_department(user_id, user_info, resource, db)
            elif condition == "is_approver":
                return await self._check_is_approver(user_id, resource, db)
            elif condition == "is_self":
                target_user_id = resource.get("user_id") or resource.get("target_user_id")
                return user_id == target_user_id
            else:
                logger.warning(f"Unknown permission condition: {condition}")
                return False
        except Exception as e:
            logger.error(f"Condition evaluation error ({condition}): {e}")
            return False

    async def _check_is_owner(
        self, user_id: str, resource: Dict[str, Any], db
    ) -> bool:
        """检查用户是否是资源的所有者"""
        # 先从 resource 字典直接获取
        owner_id = (
            resource.get("created_by")
            or resource.get("owner_id")
            or resource.get("submitted_by")
            or resource.get("uploaded_by")
        )
        if owner_id:
            return user_id == owner_id

        # 如果 resource 包含 table 和 id，从数据库查询
        table = resource.get("table")
        resource_id = resource.get("id")
        if table and resource_id:
            try:
                result = await db.table(table).select(
                    "created_by, owner_id, submitted_by, uploaded_by"
                ).eq("id", resource_id).maybe_single().execute()

                if result.data:
                    return user_id in [
                        result.data.get("created_by"),
                        result.data.get("owner_id"),
                        result.data.get("submitted_by"),
                        result.data.get("uploaded_by"),
                    ]
            except Exception as e:
                logger.error(f"is_owner DB check failed: {e}")

        return False

    async def _check_same_department(
        self,
        user_id: str,
        user_info: Dict[str, Any],
        resource: Dict[str, Any],
        db,
    ) -> bool:
        """检查用户与目标是否属于同一部门"""
        user_dept = user_info.get("department")
        if not user_dept:
            return False

        # 从 resource 获取目标部门
        target_dept = resource.get("department")
        if target_dept:
            return user_dept == target_dept

        # 如果 resource 包含 target_user_id，从数据库查询
        target_user_id = resource.get("user_id") or resource.get("target_user_id")
        if target_user_id:
            try:
                target_info = await self._get_user_info(target_user_id, db)
                if target_info:
                    return user_dept == target_info.get("department")
            except Exception as e:
                logger.error(f"same_department check failed: {e}")

        return False

    async def _check_is_approver(
        self, user_id: str, resource: Dict[str, Any], db
    ) -> bool:
        """检查用户是否是某审批请求的审批人"""
        approval_id = resource.get("id") or resource.get("approval_id")
        if not approval_id:
            return False

        try:
            # 检查 approval_steps 表
            result = await db.table("approval_steps").select("id").eq(
                "approval_request_id", approval_id
            ).eq("approver_id", user_id).maybe_single().execute()

            if result.data:
                return True

            # 也检查 approval_requests 表的 current_approver_id
            req_result = await db.table("approval_requests").select(
                "current_approver_id"
            ).eq("id", approval_id).maybe_single().execute()

            if req_result.data:
                return req_result.data.get("current_approver_id") == user_id

        except Exception as e:
            logger.error(f"is_approver check failed: {e}")

        return False

    # ============== 内部工具 ==============

    async def _get_user_info(self, user_id: str, db) -> Optional[Dict[str, Any]]:
        """获取用户信息（带缓存）"""
        cache_key = f"user:{user_id}:info"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            result = await db.table("users").select(
                "id, role, department, name, email"
            ).eq("id", user_id).maybe_single().execute()

            if result.data:
                self._cache.set(cache_key, result.data)
                return result.data
        except Exception as e:
            logger.error(f"Failed to fetch user info for {user_id}: {e}")

        return None

    def _role_has_hierarchy_access(self, user_role: str, allowed_roles: List[str]) -> bool:
        """
        检查用户角色是否通过层级继承拥有权限。
        高层级角色自动拥有低层级角色的权限。
        """
        user_level = self.ROLE_HIERARCHY.get(user_role, 0)
        if user_level == 0:
            return False

        # 找出允许角色中的最高层级
        max_allowed_level = max(
            self.ROLE_HIERARCHY.get(r, 0) for r in allowed_roles
        )

        # 如果用户层级 >= 最高允许层级，则自动获得权限
        return user_level >= max_allowed_level

    def invalidate_user_cache(self, user_id: str) -> None:
        """使指定用户的权限缓存失效（角色变更时调用）"""
        self._cache.invalidate_user(user_id)

    def clear_cache(self) -> None:
        """清空所有权限缓存"""
        self._cache.clear()


# ============== 全局单例 ==============

permission_service = PermissionService()
