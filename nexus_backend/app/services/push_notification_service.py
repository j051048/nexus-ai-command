"""
Web Push 推送通知服务

提供 VAPID 密钥管理、订阅注册/注销、推送发送功能。
pywebpush 为可选依赖，未安装时推送静默跳过。
"""

import json
import logging

from app.core.config import settings
from app.core.database import supabase

logger = logging.getLogger(__name__)


class PushNotificationService:
    """Web Push 推送服务"""

    def __init__(self):
        self._vapid_private_key: str | None = None
        self._vapid_public_key: str | None = None
        self._initialized = False

    def init(self):
        """初始化 VAPID 密钥"""
        self._vapid_private_key = getattr(settings, "VAPID_PRIVATE_KEY", None)
        self._vapid_public_key = getattr(settings, "VAPID_PUBLIC_KEY", None)
        if self._vapid_private_key and self._vapid_public_key:
            self._initialized = True
            logger.info("Push notification service initialized")
        else:
            logger.info("Push notification service disabled (no VAPID keys)")

    @property
    def vapid_public_key(self) -> str | None:
        """返回 VAPID 公钥（前端订阅时需要）"""
        return self._vapid_public_key

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    async def subscribe(
        self,
        user_id: str,
        subscription: dict,
        org_id: str | None = None,
        user_agent: str | None = None,
        db=None,
    ) -> dict:
        """注册推送订阅"""
        client = db or supabase
        if not client:
            return {"success": False, "error": "Database unavailable"}

        try:
            data = {
                "user_id": user_id,
                "organization_id": org_id,
                "endpoint": subscription["endpoint"],
                "p256dh": subscription["keys"]["p256dh"],
                "auth": subscription["keys"]["auth"],
                "user_agent": user_agent,
            }

            result = (
                await client.table("push_subscriptions")
                .upsert(data, on_conflict="user_id,endpoint")
                .execute()
            )

            return {
                "success": True,
                "id": result.data[0]["id"] if result.data else None,
            }
        except Exception as e:
            logger.error(f"Failed to save push subscription: {e}")
            return {"success": False, "error": str(e)}

    async def unsubscribe(self, user_id: str, endpoint: str, db=None) -> bool:
        """取消推送订阅"""
        client = db or supabase
        if not client:
            return False

        try:
            await client.table("push_subscriptions").delete().eq("user_id", user_id).eq(
                "endpoint", endpoint
            ).execute()
            return True
        except Exception as e:
            logger.error(f"Failed to delete push subscription: {e}")
            return False

    async def send_to_user(
        self,
        user_id: str,
        title: str,
        body: str,
        data: dict | None = None,
        db=None,
    ) -> int:
        """向用户的所有设备发送推送"""
        if not self._initialized:
            logger.debug("Push not initialized, skipping")
            return 0

        client = db or supabase
        if not client:
            return 0

        try:
            result = (
                await client.table("push_subscriptions")
                .select("*")
                .eq("user_id", user_id)
                .execute()
            )
            subscriptions = result.data or []
        except Exception as e:
            logger.error(f"Failed to fetch push subscriptions: {e}")
            return 0

        sent = 0
        for sub in subscriptions:
            try:
                self._send_push(sub, title, body, data)
                sent += 1
            except Exception as e:
                logger.warning(f"Push failed for {sub['endpoint'][:50]}: {e}")
                # 推送失败（可能订阅已过期），删除订阅
                if "410" in str(e) or "404" in str(e):
                    try:
                        await client.table("push_subscriptions").delete().eq(
                            "id", sub["id"]
                        ).execute()
                        logger.info(f"Removed expired subscription {sub['id']}")
                    except Exception as del_err:
                        logger.warning(f"Failed to delete expired sub: {del_err}")

        return sent

    async def send_to_org(
        self,
        org_id: str,
        title: str,
        body: str,
        data: dict | None = None,
        db=None,
    ) -> int:
        """向组织中所有用户发送推送"""
        if not self._initialized:
            return 0

        client = db or supabase
        if not client:
            return 0

        try:
            result = (
                await client.table("push_subscriptions")
                .select("user_id")
                .eq("organization_id", org_id)
                .execute()
            )
            user_ids = list({row["user_id"] for row in (result.data or [])})
        except Exception as e:
            logger.error(f"Failed to fetch org subscriptions: {e}")
            return 0

        total_sent = 0
        for uid in user_ids:
            total_sent += await self.send_to_user(uid, title, body, data, db)

        return total_sent

    def _send_push(
        self,
        subscription: dict,
        title: str,
        body: str,
        data: dict | None = None,
    ):
        """发送单条 Web Push"""
        try:
            from pywebpush import webpush

            payload = json.dumps(
                {
                    "title": title,
                    "body": body,
                    "data": data or {},
                    "icon": "/logo192.png",
                    "badge": "/logo192.png",
                }
            )

            webpush(
                subscription_info={
                    "endpoint": subscription["endpoint"],
                    "keys": {
                        "p256dh": subscription["p256dh"],
                        "auth": subscription["auth"],
                    },
                },
                data=payload,
                vapid_private_key=self._vapid_private_key,
                vapid_claims={
                    "sub": f"mailto:{getattr(settings, 'SMTP_FROM', 'noreply@nexus.ai')}"
                },
            )
        except ImportError:
            logger.debug("pywebpush not installed, push notification skipped")
        except Exception:
            raise


push_notification_service = PushNotificationService()
