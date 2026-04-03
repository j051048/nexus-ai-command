"""Admin endpoints for RAG pipeline management and evaluation."""

import logging

from fastapi import APIRouter, Depends

from app.core.auth import get_current_user_id
from app.core.dependencies import require_role
from app.core.errors import ErrorCode, api_error, api_success

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/admin/rag", tags=["Admin RAG"])


@router.post("/evaluate")
async def evaluate_rag(
    user_id: str = Depends(get_current_user_id),
    _=Depends(require_role("admin")),
):
    """
    Run RAG evaluation with built-in test dataset.
    Returns retrieval quality metrics (keyword hit rate, retrieval rate, per-category breakdown).
    If RAGAS is installed, also returns faithfulness and relevancy scores.
    """
    from app.services.rag_evaluator import rag_evaluator

    # Use the same QA pairs from test suite
    eval_qa_pairs = [
        {"query": "公司的差旅报销标准是什么？", "expected_keywords": ["报销", "差旅", "住宿"], "category": "policy"},
        {"query": "销售流程有哪些步骤？", "expected_keywords": ["销售", "流程", "线索"], "category": "process"},
        {"query": "年终奖发放规则是什么？", "expected_keywords": ["年终奖", "绩效", "薪资"], "category": "hr"},
        {"query": "如何申请加班？", "expected_keywords": ["加班", "申请"], "category": "hr"},
        {"query": "客户拜访需要准备什么材料？", "expected_keywords": ["拜访", "客户", "材料"], "category": "sales"},
        {"query": "库存查询怎么操作？", "expected_keywords": ["库存", "查询"], "category": "operations"},
        {"query": "合同审批流程是怎样的？", "expected_keywords": ["合同", "审批"], "category": "process"},
        {"query": "产品定价策略有哪些？", "expected_keywords": ["定价", "价格", "策略"], "category": "sales"},
        {"query": "新员工入职需要提交什么文件？", "expected_keywords": ["入职", "员工", "文件"], "category": "hr"},
        {"query": "CRM系统怎么录入客户信息？", "expected_keywords": ["CRM", "客户", "录入"], "category": "operations"},
    ]

    try:
        result = await rag_evaluator.evaluate_retrieval(
            eval_qa_pairs, org_id="eval", user_id=user_id
        )
        return api_success(data=result)
    except Exception as e:
        logger.error(f"RAG evaluation failed: {e}")
        raise api_error(ErrorCode.INTERNAL_ERROR, "RAG 评估失败")
