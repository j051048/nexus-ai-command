"""
证照管理服务
提供证照查询、创建、到期预警、续期等功能
"""

import logging
from datetime import UTC, datetime, timedelta

logger = logging.getLogger(__name__)


class CertificateService:
    """证照管理服务"""

    async def list_certificates(
        self,
        org_id: str,
        filters: dict | None = None,
        db=None,
    ) -> list[dict]:
        """
        查询证照列表

        Args:
            org_id: 组织ID
            filters: 筛选条件 {cert_type, holder_type, holder_id, status}
            db: 数据库客户端

        Returns:
            证照列表
        """
        if not db:
            raise RuntimeError("数据库连接不可用")

        try:
            query = (
                db.table("certificates")
                .select("*")
                .eq("organization_id", org_id)
                .order("expire_date", desc=False)
            )

            if filters:
                if filters.get("cert_type"):
                    query = query.eq("cert_type", filters["cert_type"])
                if filters.get("holder_type"):
                    query = query.eq("holder_type", filters["holder_type"])
                if filters.get("holder_id"):
                    query = query.eq("holder_id", filters["holder_id"])
                if filters.get("status"):
                    query = query.eq("status", filters["status"])

            result = await query.execute()
            return result.data or []

        except Exception as e:
            logger.error(f"查询证照列表失败: {e}")
            raise

    async def create_certificate(
        self,
        org_id: str,
        data: dict,
        db=None,
    ) -> dict:
        """
        创建证照

        Args:
            org_id: 组织ID
            data: 证照数据
            db: 数据库客户端

        Returns:
            证照对象
        """
        if not db:
            raise RuntimeError("数据库连接不可用")

        try:
            data["organization_id"] = org_id
            data.setdefault("status", "valid")

            result = await db.table("certificates").insert(data).execute()

            if result.data and len(result.data) > 0:
                logger.info(f"证照已创建: org={org_id}, type={data.get('cert_type')}")
                return result.data[0]

            raise RuntimeError("证照创建失败")

        except Exception as e:
            logger.error(f"创建证照失败: {e}")
            raise

    async def get_expiring_certs(
        self,
        org_id: str,
        days: int = 30,
        db=None,
    ) -> list[dict]:
        """
        获取即将到期的证照

        Args:
            org_id: 组织ID
            days: 预警天数（默认30天）
            db: 数据库客户端

        Returns:
            即将到期的证照列表
        """
        if not db:
            raise RuntimeError("数据库连接不可用")

        try:
            now = datetime.now(UTC)
            deadline = now + timedelta(days=days)

            result = await (
                db.table("certificates")
                .select("*")
                .eq("organization_id", org_id)
                .eq("status", "valid")
                .gte("expire_date", now.date().isoformat())
                .lte("expire_date", deadline.date().isoformat())
                .order("expire_date", desc=False)
                .execute()
            )

            return result.data or []

        except Exception as e:
            logger.error(f"获取到期证照失败: {e}")
            raise

    async def renew_certificate(
        self,
        cert_id: str,
        new_expire_date: str,
        attachment_url: str | None = None,
        db=None,
    ) -> dict:
        """
        续期证照

        Args:
            cert_id: 证照ID
            new_expire_date: 新到期日期
            attachment_url: 附件URL
            db: 数据库客户端

        Returns:
            更新后的证照对象
        """
        if not db:
            raise RuntimeError("数据库连接不可用")

        try:
            updates: dict = {
                "expire_date": new_expire_date,
                "status": "valid",
            }
            if attachment_url:
                updates["attachment_url"] = attachment_url

            result = (
                await db.table("certificates")
                .update(updates)
                .eq("id", cert_id)
                .execute()
            )

            if result.data and len(result.data) > 0:
                logger.info(f"证照已续期: id={cert_id}, new_expire={new_expire_date}")
                return result.data[0]

            raise RuntimeError("证照续期失败")

        except Exception as e:
            logger.error(f"续期证照失败: {e}")
            raise


certificate_service = CertificateService()
