"""
审计日志查询工具
暴露 AuditLogger.query_logs() 给 Agent，支持安全审计场景。
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from .base_tool import BaseTool

logger = logging.getLogger(__name__)


class QueryAuditLogsTool(BaseTool):
    """查询审计日志"""

    name = "query_audit_logs"
    description = (
        "查询系统审计日志，支持按时间、用户、操作类型和目标表筛选"
    )

    parameters = {
        "type": "object",
        "properties": {
            "days": {
                "type": "integer",
                "description": "查询最近N天的日志，默认7天",
                "default": 7,
            },
            "action": {
                "type": "string",
                "description": "操作类型过滤，如: auth.login, auth.failed, data.export, data.sensitive_access, approval.approve, ai.tool_execute",
            },
            "user_id": {
                "type": "string",
                "description": "按操作人ID过滤",
            },
            "target_table": {
                "type": "string",
                "description": "按目标表过滤，如: customers, contracts, approval_requests",
            },
            "limit": {
                "type": "integer",
                "description": "返回条数上限，默认50",
                "default": 50,
            },
        },
        "required": [],
    }

    domain = "admin"
    required_role = "boss"
    examples = [
        {"input": {"days": 7, "action": "auth.failed"}, "output_summary": "返回最近7天内所有登录失败的审计记录及异常检测摘要"},
        {"input": {"target_table": "contracts", "limit": 20}, "output_summary": "返回合同表相关的最近操作记录，最多20条"},
        {"input": {"user_id": "abc123", "days": 30}, "output_summary": "返回指定用户最近30天的所有操作记录"},
    ]
    gotchas = "仅管理员角色可用。查询天数默认7天，最大90天。返回结果包含异常检测摘要。"
    related_tools = ["get_company_stats"]

    async def run(self, args: dict[str, Any], user_id: str, config: dict[str, Any] = None) -> str:
        from app.services.audit_logger import audit_logger

        org_id = config.get("org_id") if config else None
        days = args.get("days", 7)
        action = args.get("action")
        target_user_id = args.get("user_id")
        target_table = args.get("target_table")
        limit = min(args.get("limit", 50), 100)

        now = datetime.now(timezone.utc)
        start_date = now - timedelta(days=days)

        try:
            logs = await audit_logger.query_logs(
                user_id=target_user_id,
                action=action,
                target_table=target_table,
                start_date=start_date,
                end_date=now,
                org_id=org_id,
                limit=limit,
            )

            if not logs:
                return f"最近 {days} 天内没有找到匹配的审计日志。"

            # 汇总统计
            action_counts: dict[str, int] = {}
            status_counts: dict[str, int] = {"success": 0, "failed": 0, "warning": 0}
            user_counts: dict[str, int] = {}

            for log in logs:
                a = log.get("action", "unknown")
                action_counts[a] = action_counts.get(a, 0) + 1
                s = log.get("status", "success")
                if s in status_counts:
                    status_counts[s] += 1
                uid = log.get("actor_user_id", "unknown")
                user_counts[uid] = user_counts.get(uid, 0) + 1

            summary = {
                "total_records": len(logs),
                "time_range": f"最近{days}天",
                "action_distribution": action_counts,
                "status_distribution": status_counts,
                "top_users": dict(sorted(user_counts.items(), key=lambda x: x[1], reverse=True)[:5]),
            }

            # 标记异常
            alerts = []
            failed_count = status_counts.get("failed", 0)
            if failed_count > 5:
                alerts.append(f"⚠️ 发现 {failed_count} 次失败操作，建议关注")

            auth_failed = action_counts.get("auth.failed", 0)
            if auth_failed > 3:
                alerts.append(f"🔒 发现 {auth_failed} 次登录失败，可能存在暴力破解风险")

            data_exports = action_counts.get("data.export", 0)
            if data_exports > 0:
                alerts.append(f"📤 发现 {data_exports} 次数据导出操作")

            # 最近的日志详情（取前10条）
            recent = []
            for log in logs[:10]:
                recent.append({
                    "time": log.get("timestamp", ""),
                    "action": log.get("action", ""),
                    "user": log.get("actor_user_id", "")[:8] + "..." if log.get("actor_user_id") else "system",
                    "status": log.get("status", ""),
                    "target": log.get("target_table", ""),
                    "ip": log.get("ip_address", ""),
                })

            result = {
                "summary": summary,
                "alerts": alerts if alerts else ["✅ 未发现明显异常"],
                "recent_logs": recent,
            }

            return json.dumps(result, ensure_ascii=False, indent=2)

        except Exception as e:
            logger.error(f"[AuditTool] Query failed: {e}")
            return f"❌ 审计日志查询失败: {str(e)}"
