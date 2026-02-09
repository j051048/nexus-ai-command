from .base_tool import BaseTool
from typing import Dict, Any
from app.core.database import supabase

# AI Assistant 固定 UUID
AI_ASSISTANT_ID = "00000000-0000-0000-0000-000000000001"


class SubmitApprovalOnBehalfTool(BaseTool):
    """AI助手代员工提交审批申请 - 自动使用当前登录用户的身份"""
    name = "submit_approval_on_behalf"
    description = "代表当前用户提交审批申请（出差、请假、报销等）。无需传入员工ID，系统会自动使用当前登录用户的身份。"
    required_role = "ai_assistant"  # 允许通过 AI 调用

    parameters = {
        "type": "object",
        "properties": {
            "type": {
                "type": "string", 
                "enum": ["travel", "leave", "expense", "purchase"],
                "description": "审批类型：travel=出差, leave=请假, expense=报销, purchase=采购"
            },
            "amount": {"type": "number", "description": "金额（如适用，默认0）"},
            "description": {"type": "string", "description": "详细说明申请事由"},
            "start_date": {"type": "string", "description": "开始日期（如适用）"},
            "end_date": {"type": "string", "description": "结束日期（如适用）"}
        },
        "required": ["type", "description"]
    }

    async def run(self, args: Dict[str, Any], user_id: str, config: Dict[str, Any] = None) -> str:
        # 使用当前登录用户的 ID（从 JWT 解析出来的）
        employee_id = user_id
        approval_type = args.get("type")
        amount = args.get("amount", 0)
        description = args.get("description")
        start_date = args.get("start_date", "")
        end_date = args.get("end_date", "")

        print(f"[AI审批] 当前用户ID: {user_id}, 申请类型: {approval_type}")

        # 验证员工存在
        employee_check = await supabase.table("users").select("id, name, role").eq("id", employee_id).single().execute()
        if not employee_check.data:
            return f"错误：找不到您的用户信息（ID: {employee_id}）"
        
        actual_employee = employee_check.data
        employee_name = actual_employee.get("name", "未知")
        
        if actual_employee.get("role") == "founder":
            return "错误：老板无需通过AI提交审批申请，您可以直接审批"

        # 构建详情
        full_details = description
        if start_date or end_date:
            full_details += f"\n日期：{start_date} 至 {end_date}"

                # 插入审批记录 - 关键：submitted_by 是员工ID，不是AI的ID
        try:
            insert_data = {
                "submitted_by": employee_id,  # 归属于员工
                "on_behalf_of": employee_id,
                "submitted_via": "ai_assistant",
                "type": approval_type,
                "amount": amount,
                "description": full_details,
                "status": "pending",
                "ai_reason": f"由AI助手豆豆代{actual_employee.get('name', employee_name)}提交"
            }
            print(f"[AI审批] 准备插入数据: {insert_data}")
            
            result = await supabase.table("approval_requests").insert(insert_data).execute()
            print(f"[AI审批] 插入结果: {result}")
        except Exception as e:
            print(f"[AI审批] 插入失败: {e}")
            return f"提交失败：数据库错误 - {str(e)}"

        if result.data:
            req_id = result.data[0].get("id")
            # 记录审计日志
            await supabase.table("audit_logs").insert({
                "action": "approval_submitted_via_ai",
                "actor_user_id": AI_ASSISTANT_ID,
                "target_id": req_id,
                "target_table": "approval_requests",
                "details_json": {
                    "employee_id": employee_id,
                    "employee_name": actual_employee.get("name"),
                    "type": approval_type,
                    "amount": amount
                }
            }).execute()
            
            return f"✅ 已成功为您（{employee_name}）提交{approval_type}申请（单号：{req_id[:8]}...）。老板会在审批中心看到这个申请，申请人显示为您的名字。"
        
        return "提交失败，请稍后重试。"


class GetEmployeeInfoTool(BaseTool):
    """AI助手查询员工信息"""
    name = "get_employee_info"
    description = "根据员工姓名查询其ID和基本信息，用于后续代理操作"
    required_role = "ai_assistant"

    parameters = {
        "type": "object",
        "properties": {
            "employee_name": {"type": "string", "description": "员工姓名"}
        },
        "required": ["employee_name"]
    }

    async def run(self, args: Dict[str, Any], user_id: str, config: Dict[str, Any] = None) -> str:
        name = args.get("employee_name")
        result = await supabase.table("users").select("id, name, department, role").ilike("name", f"%{name}%").execute()
        
        if not result.data:
            return f"找不到名为 '{name}' 的员工。"
        
        employees = []
        for emp in result.data:
            if emp.get("role") != "founder":  # 不返回老板信息
                employees.append(f"- {emp['name']}（ID: {emp['id']}, 部门: {emp.get('department', '未知')}）")
        
        if not employees:
            return f"找不到名为 '{name}' 的普通员工。"
        
        return "找到以下员工：\n" + "\n".join(employees)


class GetEmployeeApprovalHistoryTool(BaseTool):
    """AI助手查询员工的审批历史"""
    name = "get_employee_approval_history"
    description = "查询指定员工的审批申请历史记录"
    required_role = "ai_assistant"

    parameters = {
        "type": "object",
        "properties": {
            "employee_id": {"type": "string", "description": "员工ID"},
            "limit": {"type": "integer", "description": "返回记录数量，默认5条"}
        },
        "required": ["employee_id"]
    }

    async def run(self, args: Dict[str, Any], user_id: str, config: Dict[str, Any] = None) -> str:
        employee_id = args.get("employee_id")
        limit = args.get("limit", 5)
        
        result = await supabase.table("approval_requests").select("*").eq("submitted_by", employee_id).order("created_at", desc=True).limit(limit).execute()
        
        if not result.data:
            return "该员工暂无审批记录。"
        
        records = []
        for item in result.data:
            via = "(AI代提交)" if item.get("submitted_via") == "ai_assistant" else ""
            records.append(
                f"- [{item['status']}] {item['type']} ¥{item.get('amount', 0)} {via}\n  {item.get('description', '')[:50]}..."
            )
        
        return f"最近{len(records)}条审批记录：\n" + "\n".join(records)


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
        result = await supabase.table("approval_requests").update({"status": "approved"}).eq("id", req_id).execute()
        if result.data:
            try:
                target_user = result.data[0].get("submitted_by")
                await supabase.table("notifications").insert({
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
        result = await supabase.table("approval_requests").update({"status": "rejected"}).eq("id", req_id).execute()
        if result.data:
            try:
                target_user = result.data[0].get("submitted_by")
                await supabase.table("notifications").insert({
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
        result = await supabase.table("approval_requests").select("*, users:submitted_by(name)").eq("status", "pending").execute()
        if not result.data:
            return "当前没有任何待处理的审批。"
        items = []
        for item in result.data:
            user_name = item.get("users", {}).get("name", "未知用户")
            items.append(f"ID: {item['id']}, 申请人: {user_name}, 类型: {item['type']}, 金额: ¥{item['amount']}, 描述: {item['description']}")
        return "待处理清单：\n" + "\n".join(items)
