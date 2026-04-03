"""
证照管理工具集
提供证照查询、登记、到期提醒、续期等功能
"""

import logging
from typing import Any

from app.services.certificate_service import certificate_service
from app.tools._shared import safe_tool_error

from ._shared import _get_client, _validate_uuid
from .base_tool import BaseTool

logger = logging.getLogger(__name__)


def _get_org_id(config: dict = None) -> str | None:
    return config.get("org_id") if config else None


# ============================================================================
# 证照管理工具
# ============================================================================


class ListCertificatesTool(BaseTool):
    """查询证照列表"""

    name = "list_certificates"
    description = "查询证照列表，支持按类型和持有者筛选。当用户说'查看证照'、'证照列表'时调用。"
    domain = "admin"
    examples = [
        {"input": {}, "output_summary": "返回全部证照列表"},
        {"input": {"holder_type": "company"}, "output_summary": "返回公司持有的全部证照"},
        {"input": {"cert_type": "营业执照", "holder_type": "company"}, "output_summary": "返回公司持有的营业执照"},
    ]
    related_tools = ["create_certificate", "expiring_certificates", "renew_certificate"]
    gotchas = "holder_type只支持company和employee两个值。holder_id必须是有效的UUID格式。"

    parameters = {
        "type": "object",
        "properties": {
            "cert_type": {
                "type": "string",
                "description": "证照类型（可选）",
            },
            "holder_type": {
                "type": "string",
                "description": "持有者类型",
                "enum": ["company", "employee"],
            },
            "holder_id": {
                "type": "string",
                "description": "持有者ID（可选）",
            },
        },
        "required": [],
    }

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        client = _get_client(config)
        org_id = _get_org_id(config)
        if not org_id:
            return "❌ 无法获取组织信息，请确保已正确登录。"

        filters = {}
        if args.get("cert_type"):
            filters["cert_type"] = args["cert_type"]
        if args.get("holder_type"):
            filters["holder_type"] = args["holder_type"]
        if args.get("holder_id"):
            if err := _validate_uuid(args["holder_id"], "holder_id"):
                return f"❌ {err}"
            filters["holder_id"] = args["holder_id"]

        try:
            certs = await certificate_service.list_certificates(
                org_id=org_id,
                filters=filters or None,
                db=client,
            )

            if not certs:
                return "📋 当前暂无证照记录。"

            status_labels = {
                "valid": "有效",
                "expired": "已过期",
                "revoked": "已吊销",
            }
            holder_labels = {
                "company": "公司",
                "employee": "员工",
            }

            lines = [f"📜 共找到 {len(certs)} 个证照:\n"]
            for cert in certs:
                status = status_labels.get(cert.get("status", ""), cert.get("status", ""))
                holder = holder_labels.get(cert.get("holder_type", ""), cert.get("holder_type", ""))
                expire = str(cert.get("expire_date", "无期限"))[:10]
                lines.append(
                    f"- **{cert.get('name', '未知')}** | 类型: {cert.get('cert_type', '未知')} | "
                    f"持有者: {holder} | 状态: {status} | "
                    f"到期: {expire} | ID: {cert['id'][:8]}..."
                )

            return "\n".join(lines)

        except Exception as e:
            logger.error(f"查询证照列表失败: {e}")
            return safe_tool_error(e, "查询证照列表")


class CreateCertificateTool(BaseTool):
    """创建证照记录"""

    name = "create_certificate"
    description = "创建新的证照登记记录，需要管理员权限。当用户说'登记证照'、'添加证照'时调用。"
    domain = "admin"
    examples = [
        {
            "input": {
                "cert_type": "营业执照",
                "cert_no": "BL-2024-001",
                "name": "营业执照",
                "holder_type": "company",
                "holder_id": "uuid-xxx",
                "issue_date": "2024-01-01",
                "expire_date": "2029-01-01",
            },
            "output_summary": "创建一条营业执照记录",
        },
    ]
    related_tools = ["list_certificates", "renew_certificate", "expiring_certificates"]
    gotchas = "所有字段均为必填。日期格式必须为YYYY-MM-DD。holder_id必须是有效的UUID。需要admin角色权限。"

    required_role = "admin"

    parameters = {
        "type": "object",
        "properties": {
            "cert_type": {
                "type": "string",
                "description": "证照类型",
            },
            "cert_no": {
                "type": "string",
                "description": "证照编号",
            },
            "name": {
                "type": "string",
                "description": "证照名称",
                "maxLength": 100,
            },
            "holder_type": {
                "type": "string",
                "description": "持有者类型",
                "enum": ["company", "employee"],
            },
            "holder_id": {
                "type": "string",
                "description": "持有者ID",
            },
            "issue_date": {
                "type": "string",
                "description": "发证日期 YYYY-MM-DD",
            },
            "expire_date": {
                "type": "string",
                "description": "到期日期 YYYY-MM-DD",
            },
        },
        "required": ["cert_type", "cert_no", "name", "holder_type", "holder_id", "issue_date", "expire_date"],
    }

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        client = _get_client(config)
        org_id = _get_org_id(config)
        if not org_id:
            return "❌ 无法获取组织信息，请确保已正确登录。"

        name = args.get("name", "").strip()
        cert_type = args.get("cert_type", "").strip()
        cert_no = args.get("cert_no", "").strip()
        holder_type = args.get("holder_type", "").strip()
        holder_id = args.get("holder_id", "").strip()
        issue_date = args.get("issue_date", "").strip()
        expire_date = args.get("expire_date", "").strip()

        if not all([name, cert_type, cert_no, holder_type, holder_id, issue_date, expire_date]):
            return "❌ 所有必填字段不能为空"

        if err := _validate_uuid(holder_id, "holder_id"):
            return f"❌ {err}"

        data = {
            "cert_type": cert_type,
            "cert_no": cert_no,
            "name": name,
            "holder_type": holder_type,
            "holder_id": holder_id,
            "issue_date": issue_date,
            "expire_date": expire_date,
        }

        try:
            cert = await certificate_service.create_certificate(
                org_id=org_id,
                data=data,
                db=client,
            )

            return (
                f"✅ 证照创建成功！\n\n"
                f"- 名称: {name}\n"
                f"- 类型: {cert_type}\n"
                f"- 编号: {cert_no}\n"
                f"- 到期日期: {expire_date}\n"
                f"- ID: {cert['id']}"
            )

        except Exception as e:
            logger.error(f"创建证照失败: {e}")
            return safe_tool_error(e, "创建证照")


class ExpiringCertsTool(BaseTool):
    """获取即将到期的证照"""

    name = "expiring_certificates"
    description = "查询指定天数内即将到期的证照。当用户说'证照到期'、'哪些证照快到期了'时调用。"
    domain = "admin"
    examples = [
        {"input": {}, "output_summary": "返回未来30天内即将到期的证照（默认）"},
        {"input": {"days": 90}, "output_summary": "返回未来90天内即将到期的证照"},
    ]
    related_tools = ["list_certificates", "renew_certificate"]
    gotchas = "默认查询未来30天。days取值范围1-365。已过期的证照不会出现在结果中。"

    parameters = {
        "type": "object",
        "properties": {
            "days": {
                "type": "integer",
                "description": "提前多少天提醒（默认30天）",
                "minimum": 1,
                "maximum": 365,
            },
        },
        "required": [],
    }

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        client = _get_client(config)
        org_id = _get_org_id(config)
        if not org_id:
            return "❌ 无法获取组织信息，请确保已正确登录。"

        days = args.get("days", 30)

        try:
            certs = await certificate_service.get_expiring_certs(
                org_id=org_id,
                days=days,
                db=client,
            )

            if not certs:
                return f"✅ 未来 {days} 天内没有即将到期的证照。"

            holder_labels = {
                "company": "公司",
                "employee": "员工",
            }

            lines = [f"⚠️ 未来 {days} 天内即将到期的证照 ({len(certs)} 个):\n"]
            for cert in certs:
                holder = holder_labels.get(cert.get("holder_type", ""), cert.get("holder_type", ""))
                lines.append(
                    f"- 🔴 **{cert.get('name', '未知')}** | 类型: {cert.get('cert_type', '未知')} | "
                    f"持有者: {holder} | 到期: {str(cert.get('expire_date', ''))[:10]} | "
                    f"ID: {cert['id'][:8]}..."
                )

            return "\n".join(lines)

        except Exception as e:
            logger.error(f"查询到期证照失败: {e}")
            return safe_tool_error(e, "查询到期证照")


class RenewCertificateTool(BaseTool):
    """续期证照"""

    name = "renew_certificate"
    description = "更新证照的到期日期，执行续期操作，需要管理员权限。当用户说'续期证照'、'更新证照有效期'时调用。"
    domain = "admin"
    examples = [
        {
            "input": {"cert_id": "uuid-xxx", "new_expire_date": "2030-12-31"},
            "output_summary": "将指定证照的到期日期更新为2030-12-31",
        },
    ]
    related_tools = ["list_certificates", "expiring_certificates", "create_certificate"]
    gotchas = "cert_id必须是有效的UUID格式。new_expire_date格式为YYYY-MM-DD。需要admin角色权限。续期前建议先用expiring_certificates确认证照信息。"

    required_role = "admin"

    parameters = {
        "type": "object",
        "properties": {
            "cert_id": {
                "type": "string",
                "description": "证照ID",
            },
            "new_expire_date": {
                "type": "string",
                "description": "新到期日期 YYYY-MM-DD",
            },
        },
        "required": ["cert_id", "new_expire_date"],
    }

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        client = _get_client(config)

        cert_id = args.get("cert_id", "").strip()
        new_expire_date = args.get("new_expire_date", "").strip()

        if not cert_id or not new_expire_date:
            return "❌ 证照ID和新到期日期不能为空"

        if err := _validate_uuid(cert_id, "cert_id"):
            return f"❌ {err}"

        try:
            cert = await certificate_service.renew_certificate(
                cert_id=cert_id,
                new_expire_date=new_expire_date,
                db=client,
            )

            return (
                f"✅ 证照续期成功！\n\n"
                f"- 证照: {cert.get('name', '未知')}\n"
                f"- 新到期日期: {new_expire_date}\n"
                f"- ID: {cert['id']}"
            )

        except Exception as e:
            logger.error(f"证照续期失败: {e}")
            return safe_tool_error(e, "证照续期")
