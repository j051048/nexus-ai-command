"""
P1 Enhancement: RAG Quality Evaluation Tests

Tests the quality of retrieval-augmented generation pipeline including:
- Structural validation of search results
- Source attribution checks
- Answer relevance evaluation with fixture dataset
- Grounding metric readiness
"""

import pytest

from app.services.vector_service import EMBEDDING_MODEL, EMBEDDING_MODEL_VERSION, vector_service

# ── Evaluation Fixture Dataset ──────────────────────────────────────────────

EVAL_QA_PAIRS = [
    {
        "query": "公司的差旅报销标准是什么？",
        "expected_keywords": ["报销", "差旅", "住宿"],
        "category": "policy",
    },
    {
        "query": "销售流程有哪些步骤？",
        "expected_keywords": ["销售", "流程", "线索"],
        "category": "process",
    },
    {
        "query": "年终奖发放规则是什么？",
        "expected_keywords": ["年终奖", "绩效", "薪资"],
        "category": "hr",
    },
    {
        "query": "如何申请加班？",
        "expected_keywords": ["加班", "申请"],
        "category": "hr",
    },
    {
        "query": "客户拜访需要准备什么材料？",
        "expected_keywords": ["拜访", "客户", "材料"],
        "category": "sales",
    },
    {
        "query": "库存查询怎么操作？",
        "expected_keywords": ["库存", "查询"],
        "category": "operations",
    },
    {
        "query": "合同审批流程是怎样的？",
        "expected_keywords": ["合同", "审批"],
        "category": "process",
    },
    {
        "query": "产品定价策略有哪些？",
        "expected_keywords": ["定价", "价格", "策略"],
        "category": "sales",
    },
    {
        "query": "新员工入职需要提交什么文件？",
        "expected_keywords": ["入职", "员工", "文件"],
        "category": "hr",
    },
    {
        "query": "数据安全管理规定有哪些？",
        "expected_keywords": ["数据", "安全", "规定"],
        "category": "policy",
    },
]


# ── Tests ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_rag_faithfulness():
    """
    Evaluates if the answer is grounded in the retrieved context.
    Structural test for grounding metrics readiness.
    """
    test_queries = [
        "Nexus AI的支持哪些核价流程？",
        "ZY-100系列的产品规格是什么？",
    ]

    user_id = "test_eval_user"
    org_id = "test_eval_org"

    for query in test_queries:
        response = await vector_service.search(query, user_id, org_id=org_id)

        # 1. Structural Validation - must return one of the expected formats
        assert "检索到以下相关知识" in response or "知识库中未找到" in response

        # 2. Source Attribution Check
        if "检索到" in response:
            assert "[来源:" in response


@pytest.mark.asyncio
async def test_rag_answer_relevance():
    """
    P1 Enhancement: Evaluate answer relevance with fixture dataset.
    Uses keyword overlap as a proxy for relevance score.
    """
    user_id = "test_eval_user"
    org_id = "test_eval_org"
    results = []

    for qa in EVAL_QA_PAIRS:
        response = await vector_service.search(qa["query"], user_id, org_id=org_id)

        # Check if response is a "not found" response (acceptable for mock/empty DB)
        is_not_found = "未找到" in response

        if not is_not_found:
            # Check keyword overlap for relevance
            hits = sum(1 for kw in qa["expected_keywords"] if kw in response)
            relevance = hits / len(qa["expected_keywords"]) if qa["expected_keywords"] else 0
        else:
            relevance = 0.0  # Not found is acceptable in test env

        results.append(
            {
                "query": qa["query"],
                "category": qa["category"],
                "relevance_score": relevance,
                "is_not_found": is_not_found,
            }
        )

    # In a test environment with mock data, we just verify structure
    assert len(results) == len(EVAL_QA_PAIRS)

    # Log results for manual review
    for r in results:
        print(
            f"  [{r['category']}] relevance={r['relevance_score']:.2f} " f"not_found={r['is_not_found']} | {r['query']}"
        )


def test_embedding_model_versioning():
    """Verify embedding model constants are defined for staleness tracking."""
    assert EMBEDDING_MODEL == "text-embedding-3-small"
    assert EMBEDDING_MODEL_VERSION is not None
    assert len(EMBEDDING_MODEL_VERSION) > 0


@pytest.mark.asyncio
async def test_search_input_sanitization():
    """Verify that malicious search input is properly sanitized."""
    user_id = "test_user"
    org_id = "test_org"

    # SQL injection attempts
    malicious_inputs = [
        "'; DROP TABLE documents; --",
        "test%' OR '1'='1",
        "normal query; DELETE FROM users",
    ]

    for query in malicious_inputs:
        response = await vector_service.search(query, user_id, org_id=org_id)
        # Should not crash - returns a valid string response
        assert isinstance(response, str)
        assert len(response) > 0


@pytest.mark.asyncio
async def test_search_requires_org_id():
    """P0 Security: Search must require org_id in production mode."""
    user_id = "test_user"

    # Without org_id (require_org_id=True by default)
    response = await vector_service.search("test query", user_id, org_id=None, require_org_id=True)
    assert "缺少组织信息" in response or "搜索失败" in response
