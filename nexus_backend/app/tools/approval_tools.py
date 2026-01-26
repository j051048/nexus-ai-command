from .base_tool import BaseTool
from typing import Dict, Any
from app.core.database import supabase

class ApprovalTool(BaseTool):
    name = "approve_request"
    description = "批准一个待处理的审批申请（报销或采购）"
    required_role = "boss"  # Only boss/manager can approve

    parameters = {
        "type": "object",
        "properties": {
            "request_id": {"type": "string", "description": "审批单的唯一ID"},
            "reason": {"type": "string", "description": "批准的原因（可选）"}
        },
        "required": ["request_id"]
    }

    async def run(self, args: Dict[str, Any], user_id: str, config: Dict[str, Any] = None) -> str:
        req_id = args.get("request_id")
        result = supabase.table("approval_requests").update({"status": "approved"}).eq("id", req_id).execute()
        if result.data:
            try:
                target_user = result.data[0].get("submitted_by")
                supabase.table("notifications").insert({
                    "user_id": target_user,
                    "title": "审批已通过",
                    "content": f"您的审批申请 {req_id} 已被 AI 批准。",
                    "type": "success"
                }).execute()
            except: pass
            return f"成功批准审批单 {req_id}。"
        return "批准失败，可能单据不存在或已由他人处理。"

class RejectTool(BaseTool):
    name = "reject_request"
    description = "驳回一个待处理的审批申请"
    required_role = "boss"

    parameters = {
        "type": "object",
        "properties": {
            "request_id": {"type": "string", "description": "审批单的唯一ID"},
            "reason": {"type": "string", "description": "驳回的原因（必须说明）"}
        },
        "required": ["request_id", "reason"]
    }

    async def run(self, args: Dict[str, Any], user_id: str, config: Dict[str, Any] = None) -> str:
        req_id = args.get("request_id")
        reason = args.get("reason", "未说明原因")
        result = supabase.table("approval_requests").update({"status": "rejected"}).eq("id", req_id).execute()
        if result.data:
            try:
                target_user = result.data[0].get("submitted_by")
                supabase.table("notifications").insert({
                    "user_id": target_user,
                    "title": "审批已驳回",
                    "content": f"您的审批申请 {req_id} 已被驳回。理由：{reason}",
                    "type": "error"
                }).execute()
            except: pass
            return f"已成功驳回单据 {req_id}，理由：{reason}。"
        return "驳回失败。"

class PendingApprovalsTool(BaseTool):
    name = "get_pending_approvals"
    description = "获取当前所有待处理的异常审批列表"
    
    parameters = {
        "type": "object",
        "properties": {}
    }

    async def run(self, args: Dict[str, Any], user_id: str, config: Dict[str, Any] = None) -> str:
        result = supabase.table("approval_requests").select("*, users:submitted_by(name)").eq("status", "pending").execute()
        if not result.data:
            return "当前没有任何待处理的审批。"
        items = []
        for item in result.data:
            user_name = item.get("users", {}).get("name", "未知用户")
            items.append(f"ID: {item['id']}, 申请人: {user_name}, 类型: {item['type']}, 金额: ¥{item['amount']}, 描述: {item['description']}")
        return "待处理清单：\n" + "\n".join(items)
