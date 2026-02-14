"""
通讯录同步服务 - 从 IM 平台同步部门和用户到 Nexus

功能：
1. 从 im_platform_config 表读取平台配置
2. 创建对应的 IM 平台客户端
3. 拉取部门列表 -> 映射到 Nexus departments
4. 拉取每个部门的用户 -> 映射到 Nexus users + im_user_mappings
5. 返回同步统计
"""

import logging
from typing import Dict, List, Optional, Any

from app.core.database import supabase
from app.services.im_platform.base_client import IMPlatformClient
from app.services.im_platform.wecom_client import WecomClient
from app.services.im_platform.dingtalk_client import DingtalkClient
from app.services.im_platform.feishu_client import FeishuClient

logger = logging.getLogger(__name__)


class ContactSyncService:
    """
    通讯录同步服务。

    从 IM 平台（企微/钉钉/飞书）同步组织通讯录到 Nexus 系统，
    建立平台用户 ID 与 Nexus 用户 ID 的映射关系。
    """

    async def sync_contacts(
        self, org_id: str, platform: str, db=None
    ) -> Dict[str, Any]:
        """
        从指定 IM 平台同步通讯录到 Nexus。

        Args:
            org_id: Nexus 组织 ID
            platform: 平台标识 (wecom/dingtalk/feishu)
            db: 数据库客户端（可选，默认使用全局 supabase）

        Returns:
            同步统计信息:
            {
                "departments_synced": 10,
                "users_synced": 50,
                "users_created": 5,
                "users_updated": 45,
                "errors": []
            }
        """
        db = db or supabase
        stats = {
            "departments_synced": 0,
            "users_synced": 0,
            "users_created": 0,
            "users_updated": 0,
            "errors": [],
        }

        client = None
        try:
            client = await self._get_client(org_id, platform, db)
            if not client:
                stats["errors"].append(
                    f"Failed to create {platform} client for org {org_id}"
                )
                return stats

            # 1. 同步部门
            logger.info(
                f"[ContactSync] Starting department sync for org={org_id}, "
                f"platform={platform}"
            )
            dept_mapping = await self._sync_departments(client, org_id, db)
            stats["departments_synced"] = len(dept_mapping)

            # 2. 同步用户
            logger.info(
                f"[ContactSync] Starting user sync for org={org_id}, "
                f"platform={platform}"
            )
            user_stats = await self._sync_users(
                client, org_id, platform, dept_mapping, db
            )
            stats["users_synced"] = user_stats.get("total", 0)
            stats["users_created"] = user_stats.get("created", 0)
            stats["users_updated"] = user_stats.get("updated", 0)

            logger.info(
                f"[ContactSync] Sync complete for org={org_id}: "
                f"depts={stats['departments_synced']}, "
                f"users={stats['users_synced']}"
            )

        except Exception as e:
            error_msg = f"Contact sync error for org={org_id}: {e}"
            logger.error(f"[ContactSync] {error_msg}")
            stats["errors"].append(error_msg)
        finally:
            if client:
                await client.close()

        return stats

    async def _get_client(
        self, org_id: str, platform: str, db=None
    ) -> Optional[IMPlatformClient]:
        """
        从 im_platform_config 表获取配置并创建平台客户端。

        Args:
            org_id: 组织 ID
            platform: 平台标识
            db: 数据库客户端

        Returns:
            平台客户端实例，或 None（获取失败时）
        """
        db = db or supabase
        if not db:
            logger.error("[ContactSync] Database not available")
            return None

        try:
            result = (
                await db.table("im_platform_config")
                .select("config")
                .eq("organization_id", org_id)
                .eq("platform", platform)
                .eq("is_active", True)
                .single()
                .execute()
            )

            if not result.data:
                logger.warning(
                    f"[ContactSync] No active config found for "
                    f"org={org_id}, platform={platform}"
                )
                return None

            config = result.data.get("config", {})
            return self._create_client(platform, config)

        except Exception as e:
            logger.error(
                f"[ContactSync] Failed to get config for "
                f"org={org_id}, platform={platform}: {e}"
            )
            return None

    @staticmethod
    def _create_client(
        platform: str, config: Dict[str, Any]
    ) -> Optional[IMPlatformClient]:
        """
        根据平台和配置创建客户端实例。

        Args:
            platform: 平台标识
            config: 平台配置（从 DB 读取的 JSONB）

        Returns:
            平台客户端实例
        """
        if platform == "wecom":
            return WecomClient(
                corp_id=config.get("corp_id", ""),
                corp_secret=config.get("corp_secret", ""),
                agent_id=config.get("agent_id", ""),
            )
        elif platform == "dingtalk":
            return DingtalkClient(
                app_key=config.get("app_key", ""),
                app_secret=config.get("app_secret", ""),
                agent_id=config.get("agent_id", ""),
            )
        elif platform == "feishu":
            return FeishuClient(
                app_id=config.get("app_id", ""),
                app_secret=config.get("app_secret", ""),
            )
        else:
            logger.error(f"[ContactSync] Unknown platform: {platform}")
            return None

    async def _sync_departments(
        self, client: IMPlatformClient, org_id: str, db
    ) -> Dict[str, str]:
        """
        同步部门列表，返回平台部门 ID -> Nexus 部门 ID 映射。

        实现逻辑：
        - 拉取 IM 平台部门列表
        - 对每个部门，在 Nexus departments 表中 upsert
        - 返回映射关系

        Args:
            client: IM 平台客户端
            org_id: 组织 ID
            db: 数据库客户端

        Returns:
            {平台部门ID: Nexus部门ID}
        """
        mapping = {}
        try:
            departments = await client.get_departments()
            logger.info(
                f"[ContactSync] Fetched {len(departments)} departments "
                f"from {client.platform_name}"
            )

            for dept in departments:
                platform_dept_id = dept.get("id", "")
                dept_name = dept.get("name", "Unknown")
                parent_id = dept.get("parentid", "0")

                if not platform_dept_id:
                    continue

                try:
                    # Upsert 到 departments 表（假设表存在）
                    # 使用 organization_id + 外部来源标识 做幂等
                    dept_data = {
                        "organization_id": org_id,
                        "name": dept_name,
                        "external_id": f"{client.platform_name}:{platform_dept_id}",
                        "external_parent_id": f"{client.platform_name}:{parent_id}",
                        "source": client.platform_name,
                    }

                    result = await db.table("departments").upsert(
                        dept_data,
                        on_conflict="organization_id,external_id",
                    ).execute()

                    if result.data:
                        nexus_dept_id = result.data[0].get("id", "")
                        mapping[platform_dept_id] = nexus_dept_id

                except Exception as e:
                    logger.warning(
                        f"[ContactSync] Failed to upsert department "
                        f"{dept_name} ({platform_dept_id}): {e}"
                    )
                    # 即使某个部门失败，继续处理其他部门
                    continue

        except Exception as e:
            logger.error(f"[ContactSync] Department sync failed: {e}")

        return mapping

    async def _sync_users(
        self,
        client: IMPlatformClient,
        org_id: str,
        platform: str,
        dept_mapping: Dict[str, str],
        db,
    ) -> Dict[str, int]:
        """
        同步用户列表。

        对每个部门拉取用户，然后：
        1. 在 im_user_mappings 表查找已有映射
        2. 如果未映射，尝试通过手机号关联 Nexus 用户
        3. 创建或更新 im_user_mappings 记录

        Args:
            client: IM 平台客户端
            org_id: 组织 ID
            platform: 平台标识
            dept_mapping: 部门 ID 映射
            db: 数据库客户端

        Returns:
            {"total": N, "created": N, "updated": N}
        """
        stats = {"total": 0, "created": 0, "updated": 0}
        processed_users = set()  # 去重（用户可能在多个部门）

        for platform_dept_id, nexus_dept_id in dept_mapping.items():
            try:
                users = await client.get_department_users(platform_dept_id)
            except Exception as e:
                logger.warning(
                    f"[ContactSync] Failed to get users for dept "
                    f"{platform_dept_id}: {e}"
                )
                continue

            for user in users:
                platform_user_id = user.get("userid", "")
                if not platform_user_id or platform_user_id in processed_users:
                    continue

                processed_users.add(platform_user_id)
                stats["total"] += 1

                try:
                    # 检查是否已有映射
                    existing = (
                        await db.table("im_user_mappings")
                        .select("id, user_id")
                        .eq("organization_id", org_id)
                        .eq("platform", platform)
                        .eq("platform_user_id", platform_user_id)
                        .execute()
                    )

                    if existing.data:
                        # 更新已有映射
                        mapping_id = existing.data[0]["id"]
                        await db.table("im_user_mappings").update(
                            {
                                "platform_username": user.get("name", ""),
                                "platform_department_id": platform_dept_id,
                            }
                        ).eq("id", mapping_id).execute()
                        stats["updated"] += 1
                    else:
                        # 尝试通过手机号找到 Nexus 用户
                        nexus_user_id = await self._find_nexus_user_by_mobile(
                            user.get("mobile", ""), org_id, db
                        )

                        if nexus_user_id:
                            # 创建映射
                            await db.table("im_user_mappings").insert(
                                {
                                    "user_id": nexus_user_id,
                                    "organization_id": org_id,
                                    "platform": platform,
                                    "platform_user_id": platform_user_id,
                                    "platform_username": user.get("name", ""),
                                    "platform_department_id": platform_dept_id,
                                }
                            ).execute()
                            stats["created"] += 1
                        else:
                            logger.debug(
                                f"[ContactSync] No Nexus user found for "
                                f"platform user {platform_user_id} "
                                f"(mobile={user.get('mobile', 'N/A')})"
                            )

                except Exception as e:
                    logger.warning(
                        f"[ContactSync] Failed to sync user "
                        f"{platform_user_id}: {e}"
                    )
                    continue

        return stats

    @staticmethod
    async def _find_nexus_user_by_mobile(
        mobile: str, org_id: str, db
    ) -> Optional[str]:
        """
        通过手机号在 Nexus users 表中查找用户。

        Args:
            mobile: 手机号
            org_id: 组织 ID
            db: 数据库客户端

        Returns:
            Nexus user ID，未找到返回 None
        """
        if not mobile:
            return None

        try:
            result = (
                await db.table("users")
                .select("id")
                .eq("organization_id", org_id)
                .eq("phone", mobile)
                .limit(1)
                .execute()
            )

            if result.data:
                return result.data[0].get("id")
        except Exception as e:
            logger.debug(f"[ContactSync] User lookup by mobile failed: {e}")

        return None


# 模块级单例
contact_sync_service = ContactSyncService()
