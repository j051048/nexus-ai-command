"""
Onboarding Demo Data Generation Service.

Generates realistic sample data for new organizations so users can
immediately experience the platform features without manual data entry.

Tables populated:
  - users (employees)
  - customers (CRM)
  - projects
  - approval_requests
  - sales_leads
  - contracts
  - attendance_records
"""

import logging
import uuid
from datetime import datetime, timedelta, date
from typing import Dict, Any, List, Optional

from app.core.database import supabase

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Idempotency check & cleanup helpers
# ---------------------------------------------------------------------------

async def _demo_data_exists(db, org_id: str) -> bool:
    """Check if demo data already exists for the given organization."""
    result = await db.table("users") \
        .select("id") \
        .eq("organization_id", org_id) \
        .like("email", "%@demo.local") \
        .limit(1) \
        .execute()
    return bool(result.data)


async def cleanup_demo_data(org_id: str) -> Dict[str, int]:
    """
    Remove all demo data for a given organization.

    Deletes records tagged with ``demo`` or associated with ``@demo.local``
    employee emails.  Deletion order respects foreign-key dependencies
    (children first, employees last).

    Returns:
        Dict mapping table names to the number of deleted rows.
    """
    if not supabase:
        raise RuntimeError("Database not configured")

    db = supabase
    deleted: Dict[str, int] = {}

    # Fetch demo employee IDs first – needed for dependent tables
    emp_result = await db.table("users") \
        .select("id") \
        .eq("organization_id", org_id) \
        .like("email", "%@demo.local") \
        .execute()
    demo_emp_ids = [row["id"] for row in (emp_result.data or [])]

    # 1. Attendance records (by org + demo employee IDs)
    if demo_emp_ids:
        res = await db.table("attendance_records") \
            .delete() \
            .eq("organization_id", org_id) \
            .in_("user_id", demo_emp_ids) \
            .execute()
        deleted["attendance_records"] = len(res.data or [])

    # 2. Approval requests (by org + demo submitter IDs)
    if demo_emp_ids:
        res = await db.table("approval_requests") \
            .delete() \
            .eq("organization_id", org_id) \
            .in_("submitted_by", demo_emp_ids) \
            .execute()
        deleted["approvals"] = len(res.data or [])

    # 3. Sales leads (by demo owner IDs)
    if demo_emp_ids:
        res = await db.table("sales_leads") \
            .delete() \
            .in_("owner_id", demo_emp_ids) \
            .execute()
        deleted["sales_leads"] = len(res.data or [])

    # 4. Contracts (by org + demo tag)
    res = await db.table("contracts") \
        .delete() \
        .eq("organization_id", org_id) \
        .contains("tags", ["demo"]) \
        .execute()
    deleted["contracts"] = len(res.data or [])

    # 5. Projects (by demo owner IDs)
    if demo_emp_ids:
        res = await db.table("projects") \
            .delete() \
            .in_("owner_id", demo_emp_ids) \
            .execute()
        deleted["projects"] = len(res.data or [])

    # 6. Customers (by org + demo tag)
    res = await db.table("customers") \
        .delete() \
        .eq("organization_id", org_id) \
        .contains("tags", ["demo"]) \
        .execute()
    deleted["customers"] = len(res.data or [])

    # 7. Demo employees (last – other tables reference them)
    if demo_emp_ids:
        res = await db.table("users") \
            .delete() \
            .eq("organization_id", org_id) \
            .like("email", "%@demo.local") \
            .execute()
        deleted["employees"] = len(res.data or [])

    logger.info("[DemoData] Cleanup complete for org=%s: %s", org_id, deleted)
    return deleted

# ---------------------------------------------------------------------------
# Demo data templates
# ---------------------------------------------------------------------------

_DEMO_EMPLOYEES = [
    {"name": "张明", "email": "zhangming@demo.local", "role": "manager", "department": "sales", "title": "销售总监", "phone": "13800001001"},
    {"name": "李芳", "email": "lifang@demo.local", "role": "employee", "department": "sales", "title": "高级销售", "phone": "13800001002"},
    {"name": "王强", "email": "wangqiang@demo.local", "role": "employee", "department": "sales", "title": "销售专员", "phone": "13800001003"},
    {"name": "赵丽", "email": "zhaoli@demo.local", "role": "employee", "department": "engineering", "title": "技术经理", "phone": "13800001004"},
    {"name": "陈伟", "email": "chenwei@demo.local", "role": "employee", "department": "engineering", "title": "前端工程师", "phone": "13800001005"},
    {"name": "刘洋", "email": "liuyang@demo.local", "role": "employee", "department": "product", "title": "产品经理", "phone": "13800001006"},
    {"name": "孙悦", "email": "sunyue@demo.local", "role": "employee", "department": "hr", "title": "HR 主管", "phone": "13800001007"},
    {"name": "周敏", "email": "zhoumin@demo.local", "role": "employee", "department": "finance", "title": "财务主管", "phone": "13800001008"},
]

_DEMO_CUSTOMERS = [
    {"name": "北京锐思科技有限公司", "company": "锐思科技", "industry": "科技", "stage": "customer", "source": "线上推广", "estimated_value": 500000},
    {"name": "上海鼎丰贸易集团", "company": "鼎丰贸易", "industry": "贸易", "stage": "opportunity", "source": "行业展会", "estimated_value": 1200000},
    {"name": "深圳创新智能科技", "company": "创新智能", "industry": "人工智能", "stage": "prospect", "source": "客户转介绍", "estimated_value": 800000},
    {"name": "广州盛达物流有限公司", "company": "盛达物流", "industry": "物流", "stage": "lead", "source": "官网咨询", "estimated_value": 300000},
    {"name": "杭州云翼信息技术", "company": "云翼信息", "industry": "SaaS", "stage": "customer", "source": "渠道合作", "estimated_value": 650000},
    {"name": "成都天府数据服务", "company": "天府数据", "industry": "数据服务", "stage": "opportunity", "source": "线上推广", "estimated_value": 450000},
]

_DEMO_PROJECTS = [
    {"name": "Q1 大客户拓展计划", "description": "针对年营收过亿的潜在客户进行定向拓展", "status": "in_progress", "progress": 65},
    {"name": "CRM 系统升级项目", "description": "升级客户管理系统，集成 AI 辅助分析功能", "status": "in_progress", "progress": 40},
    {"name": "新产品发布会筹备", "description": "2025 春季新品线上发布会策划与执行", "status": "planning", "progress": 15},
    {"name": "客户满意度调研", "description": "针对核心客户进行 NPS 调研与分析", "status": "completed", "progress": 100},
]

_DEMO_APPROVALS = [
    {"type": "expense", "amount": 3500, "description": "团建餐饮费用报销", "status": "pending"},
    {"type": "travel", "amount": 8200, "description": "上海客户拜访差旅申请", "status": "pending"},
    {"type": "purchase", "amount": 15000, "description": "团队年度 SaaS 工具订阅", "status": "approved"},
    {"type": "leave", "amount": 0, "description": "年假申请 3 天（3/15-3/17）", "status": "pending"},
    {"type": "expense", "amount": 1200, "description": "客户招待晚宴费用", "status": "approved"},
]

_DEMO_CONTRACTS = [
    {"title": "锐思科技年度服务合同", "contract_type": "service", "status": "active", "amount": 480000, "days_offset": -60},
    {"title": "鼎丰贸易框架采购协议", "contract_type": "sales", "status": "pending_review", "amount": 1100000, "days_offset": -5},
    {"title": "云翼信息技术合作 NDA", "contract_type": "nda", "status": "active", "amount": 0, "days_offset": -90},
    {"title": "创新智能 POC 服务协议", "contract_type": "service", "status": "draft", "amount": 200000, "days_offset": 0},
]


async def generate_demo_data(user_id: str, org_id: str) -> Dict[str, Any]:
    """
    Generate a full set of demo data for an organization.

    Idempotent: if demo data already exists it is cleaned up before
    regeneration, preventing duplicates.

    Args:
        user_id: The authenticated user who triggered the generation.
        org_id: The organization to populate with demo data.

    Returns:
        Summary dict with counts of generated records.
    """
    if not supabase:
        raise RuntimeError("Database not configured")

    db = supabase

    # ------------------------------------------------------------------
    # Idempotency: clean up leftover demo data if it exists
    # ------------------------------------------------------------------
    if await _demo_data_exists(db, org_id):
        logger.info("[DemoData] Existing demo data detected for org=%s – cleaning up first", org_id)
        await cleanup_demo_data(org_id)

    now = datetime.utcnow()
    today = date.today()
    summary: Dict[str, int] = {}
    current_step: str = ""

    try:
        # ------------------------------------------------------------------
        # 1. Employees
        # ------------------------------------------------------------------
        current_step = "employees"
        employee_ids: List[str] = []
        for emp in _DEMO_EMPLOYEES:
            eid = str(uuid.uuid4())
            employee_ids.append(eid)
            await db.table("users").insert({
                "id": eid,
                "name": emp["name"],
                "email": emp["email"],
                "role": emp["role"],
                "department": emp["department"],
                "title": emp.get("title", ""),
                "phone": emp.get("phone", ""),
                "organization_id": org_id,
                "score": 85,
                "rank": 5,
                "total_bonus": 3000,
                "created_at": now.isoformat(),
            }).execute()
        summary["employees"] = len(employee_ids)
        logger.info("[DemoData] Created %d employees for org=%s", len(employee_ids), org_id)

        # ------------------------------------------------------------------
        # 2. Customers (CRM)
        # ------------------------------------------------------------------
        current_step = "customers"
        customer_ids: List[str] = []
        for idx, cust in enumerate(_DEMO_CUSTOMERS):
            cid = str(uuid.uuid4())
            customer_ids.append(cid)
            assigned_to = employee_ids[idx % 3]  # Assign to first 3 sales reps
            await db.table("customers").insert({
                "id": cid,
                "organization_id": org_id,
                "name": cust["name"],
                "company": cust["company"],
                "industry": cust["industry"],
                "stage": cust["stage"],
                "source": cust["source"],
                "estimated_value": cust["estimated_value"],
                "assigned_to": assigned_to,
                "tags": ["demo"],
                "created_at": now.isoformat(),
            }).execute()
        summary["customers"] = len(customer_ids)

        # ------------------------------------------------------------------
        # 3. Projects
        # ------------------------------------------------------------------
        current_step = "projects"
        for idx, proj in enumerate(_DEMO_PROJECTS):
            pid = str(uuid.uuid4())
            owner = employee_ids[idx % len(employee_ids)]
            start = now - timedelta(days=30 + idx * 15)
            end = now + timedelta(days=60 - idx * 10)
            await db.table("projects").insert({
                "id": pid,
                "name": proj["name"],
                "description": proj["description"],
                "status": proj["status"],
                "progress": proj["progress"],
                "owner_id": owner,
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "created_at": now.isoformat(),
            }).execute()
        summary["projects"] = len(_DEMO_PROJECTS)

        # ------------------------------------------------------------------
        # 4. Approval Requests
        # ------------------------------------------------------------------
        current_step = "approvals"
        for idx, appr in enumerate(_DEMO_APPROVALS):
            aid = str(uuid.uuid4())
            submitter = employee_ids[idx % len(employee_ids)]
            await db.table("approval_requests").insert({
                "id": aid,
                "submitted_by": submitter,
                "type": appr["type"],
                "amount": appr["amount"],
                "description": appr["description"],
                "status": appr["status"],
                "ai_decision": "manual",
                "organization_id": org_id,
                "created_at": (now - timedelta(days=idx * 2)).isoformat(),
            }).execute()
        summary["approvals"] = len(_DEMO_APPROVALS)

        # ------------------------------------------------------------------
        # 5. Sales Leads
        # ------------------------------------------------------------------
        current_step = "sales_leads"
        lead_data = [
            {"source_paper": "AI 赋能企业数字化白皮书", "professor": "Dr. 王教授", "match_score": 0.92, "status": "qualified"},
            {"source_paper": "供应链智能化趋势报告", "professor": "Dr. 李教授", "match_score": 0.85, "status": "new"},
            {"source_paper": "零售行业 SaaS 市场分析", "professor": "Dr. 陈教授", "match_score": 0.78, "status": "contacted"},
            {"source_paper": "制造业降本增效方案集", "professor": "Dr. 张教授", "match_score": 0.88, "status": "won"},
            {"source_paper": "金融科技合规框架研究", "professor": "Dr. 赵教授", "match_score": 0.71, "status": "new"},
        ]
        for idx, lead in enumerate(lead_data):
            lid = str(uuid.uuid4())
            await db.table("sales_leads").insert({
                "id": lid,
                "source_paper": lead["source_paper"],
                "professor": lead["professor"],
                "match_score": lead["match_score"],
                "status": lead["status"],
                "owner_id": employee_ids[idx % 3],
                "ai_win_probability": round(lead["match_score"] * 0.9, 2),
                "created_at": (now - timedelta(days=idx * 5)).isoformat(),
            }).execute()
        summary["sales_leads"] = len(lead_data)

        # ------------------------------------------------------------------
        # 6. Contracts
        # ------------------------------------------------------------------
        current_step = "contracts"
        for idx, cont in enumerate(_DEMO_CONTRACTS):
            coid = str(uuid.uuid4())
            cust_id = customer_ids[idx % len(customer_ids)]
            start_d = today + timedelta(days=cont["days_offset"])
            end_d = start_d + timedelta(days=365)
            await db.table("contracts").insert({
                "id": coid,
                "organization_id": org_id,
                "title": cont["title"],
                "customer_id": cust_id,
                "contract_number": f"CTR-{today.year}-{str(idx + 1).zfill(4)}",
                "contract_type": cont["contract_type"],
                "status": cont["status"],
                "amount": cont["amount"],
                "start_date": start_d.isoformat(),
                "end_date": end_d.isoformat(),
                "tags": ["demo"],
                "created_at": now.isoformat(),
            }).execute()
        summary["contracts"] = len(_DEMO_CONTRACTS)

        # ------------------------------------------------------------------
        # 7. Attendance Records (last 7 days for all employees) – batch insert
        # ------------------------------------------------------------------
        current_step = "attendance_records"
        attendance_batch: List[Dict[str, Any]] = []
        for emp_id in employee_ids:
            for day_offset in range(7):
                d = today - timedelta(days=day_offset)
                if d.weekday() >= 5:  # Skip weekends
                    continue
                check_in = datetime.combine(d, datetime.min.time().replace(hour=8, minute=55))
                check_out = datetime.combine(d, datetime.min.time().replace(hour=18, minute=10))
                attendance_batch.append({
                    "id": str(uuid.uuid4()),
                    "user_id": emp_id,
                    "organization_id": org_id,
                    "platform": "wecom",
                    "check_date": d.isoformat(),
                    "check_in_time": check_in.isoformat(),
                    "check_out_time": check_out.isoformat(),
                    "status": "normal",
                    "synced_at": now.isoformat(),
                })
        if attendance_batch:
            await db.table("attendance_records").insert(attendance_batch).execute()
        summary["attendance_records"] = len(attendance_batch)

    except Exception:
        logger.exception(
            "[DemoData] Failed at step '%s' for org=%s. "
            "Cleaning up partially created demo data.",
            current_step, org_id,
        )
        await cleanup_demo_data(org_id)
        raise

    logger.info("[DemoData] Generation complete for org=%s: %s", org_id, summary)
    return summary
