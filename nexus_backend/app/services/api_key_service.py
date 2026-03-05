"""
开放 API 密钥管理服务

提供 API Key 的创建、验证、列表、撤销和使用统计功能。
API Key 使用 sk-xxx 格式，仅在创建时返回完整 key，之后仅存储 SHA-256 hash。
"""

import contextlib
import hashlib
import logging
import secrets
from datetime import UTC, datetime, timedelta

logger = logging.getLogger(__name__)

# API Key 前缀
API_KEY_PREFIX = "sk-"
# Key 长度（不含前缀）
API_KEY_LENGTH = 48


class APIKeyService:
    """开放 API 密钥管理"""

    @staticmethod
    def _generate_key() -> str:
        """生成 sk-xxx 格式的 API Key"""
        random_part = secrets.token_urlsafe(API_KEY_LENGTH)
        return f"{API_KEY_PREFIX}{random_part}"

    @staticmethod
    def _hash_key(key_string: str) -> str:
        """计算 API Key 的 SHA-256 hash"""
        return hashlib.sha256(key_string.encode("utf-8")).hexdigest()

    @staticmethod
    def _get_prefix(key_string: str) -> str:
        """获取 Key 的前8位用于显示"""
        return key_string[:8] if len(key_string) >= 8 else key_string

    async def create_api_key(
        self,
        org_id: str,
        name: str,
        scopes: list[str],
        expires_days: int = 365,
        created_by: str | None = None,
        db=None,
    ) -> dict:
        """
        创建 API Key（返回完整 key 仅此一次）

        Args:
            org_id: 组织 ID
            name: Key 名称
            scopes: 权限范围列表 (read, write, admin 等)
            expires_days: 有效天数
            created_by: 创建人用户 ID
            db: 数据库客户端

        Returns:
            包含完整 key 的创建结果（仅此一次可见）
        """
        if not db:
            raise RuntimeError("数据库连接不可用")

        # 生成 key
        full_key = self._generate_key()
        key_hash = self._hash_key(full_key)
        key_prefix = self._get_prefix(full_key)

        # 计算过期时间
        expires_at = (datetime.now(UTC) + timedelta(days=expires_days)).isoformat()

        try:
            record = {
                "organization_id": org_id,
                "name": name,
                "key_hash": key_hash,
                "key_prefix": key_prefix,
                "scopes": scopes,
                "is_active": True,
                "expires_at": expires_at,
                "created_by": created_by,
            }

            result = await db.table("api_keys").insert(record).execute()

            if result.data and len(result.data) > 0:
                created = result.data[0]
                logger.info(f"API Key 已创建: org={org_id}, name={name}, prefix={key_prefix}")
                return {
                    "id": created.get("id"),
                    "name": name,
                    "key": full_key,  # 完整 key，仅此一次返回
                    "key_prefix": key_prefix,
                    "scopes": scopes,
                    "expires_at": expires_at,
                    "created_at": created.get("created_at"),
                    "warning": "请立即复制并安全保存此 API Key，它不会再次显示。",
                }

            raise RuntimeError("API Key 创建失败")

        except Exception as e:
            logger.error(f"创建 API Key 失败: {e}")
            raise

    async def validate_api_key(self, key_string: str, required_scope: str | None = None, db=None) -> dict | None:
        """
        验证 API Key 并返回关联信息

        Args:
            key_string: 完整 API Key 字符串
            required_scope: 需要的权限范围
            db: 数据库客户端

        Returns:
            验证通过时返回 key 信息，否则返回 None
        """
        if not db:
            from app.core.database import supabase

            db = supabase

        if not db:
            return None

        key_hash = self._hash_key(key_string)

        try:
            result = await (
                db.table("api_keys").select("*").eq("key_hash", key_hash).eq("is_active", True).maybe_single().execute()
            )

            if not result.data:
                return None

            key_data = result.data

            # 检查是否过期
            expires_at = key_data.get("expires_at")
            if expires_at:
                expiry = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
                if expiry < datetime.now(UTC):
                    logger.warning(f"API Key 已过期: prefix={key_data.get('key_prefix')}")
                    return None

            # 检查权限范围
            if required_scope:
                scopes = key_data.get("scopes", [])
                if required_scope not in scopes and "admin" not in scopes:
                    logger.warning(
                        f"API Key 权限不足: prefix={key_data.get('key_prefix')}, "
                        f"required={required_scope}, has={scopes}"
                    )
                    return None

            # 更新最后使用时间和使用次数
            with contextlib.suppress(Exception):
                await (
                    db.table("api_keys")
                    .update(
                        {
                            "last_used_at": datetime.now(UTC).isoformat(),
                            "usage_count": key_data.get("usage_count", 0) + 1,
                        }
                    )
                    .eq("id", key_data["id"])
                    .execute()
                )

            return {
                "key_id": key_data["id"],
                "organization_id": key_data.get("organization_id"),
                "name": key_data.get("name"),
                "scopes": key_data.get("scopes", []),
                "created_by": key_data.get("created_by"),
            }

        except Exception as e:
            logger.debug(f"API Key 验证未匹配: {e}")
            return None

    async def list_api_keys(self, org_id: str, db=None) -> list[dict]:
        """
        列出组织的 API Keys（不返回完整 key）

        Args:
            org_id: 组织 ID
            db: 数据库客户端

        Returns:
            API Key 列表
        """
        if not db:
            raise RuntimeError("数据库连接不可用")

        try:
            result = await (
                db.table("api_keys")
                .select(
                    "id, name, key_prefix, scopes, is_active, expires_at, "
                    "last_used_at, usage_count, created_by, created_at"
                )
                .eq("organization_id", org_id)
                .order("created_at", desc=True)
                .execute()
            )

            return result.data or []

        except Exception as e:
            logger.error(f"列出 API Keys 失败: {e}")
            raise

    async def revoke_api_key(self, key_id: str, db=None) -> bool:
        """
        撤销 API Key

        Args:
            key_id: Key ID
            db: 数据库客户端

        Returns:
            是否成功
        """
        if not db:
            raise RuntimeError("数据库连接不可用")

        try:
            result = await db.table("api_keys").update({"is_active": False}).eq("id", key_id).execute()

            if result.data:
                logger.info(f"API Key 已撤销: {key_id}")
                return True
            return False

        except Exception as e:
            logger.error(f"撤销 API Key 失败: {e}")
            raise

    async def get_api_usage(self, key_id: str, date_range: dict | None = None, db=None) -> dict:
        """
        获取 API Key 使用统计

        Args:
            key_id: Key ID
            date_range: 日期范围 {"from": "2026-01-01", "to": "2026-02-01"}
            db: 数据库客户端

        Returns:
            使用统计信息
        """
        if not db:
            raise RuntimeError("数据库连接不可用")

        try:
            # 获取 key 基本信息
            key_result = await (
                db.table("api_keys")
                .select("id, name, key_prefix, usage_count, last_used_at, created_at")
                .eq("id", key_id)
                .single()
                .execute()
            )

            if not key_result.data:
                return {"error": "API Key 不存在"}

            # 获取使用日志
            query = db.table("api_usage_logs").select("*").eq("api_key_id", key_id)

            if date_range:
                if date_range.get("from"):
                    query = query.gte("created_at", date_range["from"])
                if date_range.get("to"):
                    query = query.lte("created_at", date_range["to"])

            logs_result = await query.order("created_at", desc=True).limit(500).execute()
            logs = logs_result.data or []

            # 计算统计
            total_calls = len(logs)
            success_calls = sum(1 for log_entry in logs if 200 <= (log_entry.get("status_code") or 0) < 400)
            avg_response_time = (
                sum(log_entry.get("response_time_ms", 0) for log_entry in logs) / total_calls if total_calls > 0 else 0
            )

            # 按端点统计
            endpoint_stats = {}
            for log_entry in logs:
                ep = log_entry.get("endpoint", "unknown")
                if ep not in endpoint_stats:
                    endpoint_stats[ep] = {"count": 0, "errors": 0}
                endpoint_stats[ep]["count"] += 1
                status = log_entry.get("status_code") or 0
                if status >= 400:
                    endpoint_stats[ep]["errors"] += 1

            return {
                "key_info": key_result.data,
                "period_calls": total_calls,
                "success_calls": success_calls,
                "error_calls": total_calls - success_calls,
                "avg_response_time_ms": round(avg_response_time, 2),
                "endpoint_breakdown": endpoint_stats,
            }

        except Exception as e:
            logger.error(f"获取 API 使用统计失败: {e}")
            raise

    async def log_api_usage(
        self, key_id: str, endpoint: str, method: str, status_code: int, response_time_ms: int, db=None
    ) -> None:
        """
        记录 API 使用日志

        Args:
            key_id: Key ID
            endpoint: 请求端点
            method: HTTP 方法
            status_code: 响应状态码
            response_time_ms: 响应时间(ms)
            db: 数据库客户端
        """
        if not db:
            from app.core.database import supabase

            db = supabase

        if not db:
            return

        try:
            await (
                db.table("api_usage_logs")
                .insert(
                    {
                        "api_key_id": key_id,
                        "endpoint": endpoint,
                        "method": method,
                        "status_code": status_code,
                        "response_time_ms": response_time_ms,
                    }
                )
                .execute()
            )
        except Exception as e:
            logger.warning(f"记录 API 使用日志失败: {e}")


api_key_service = APIKeyService()
