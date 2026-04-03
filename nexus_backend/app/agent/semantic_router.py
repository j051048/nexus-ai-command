"""语义路由 — 用 embedding 相似度在 50ms 内完成意图分类，bypass LLM。

在关键字匹配失败后、LLM fallback 之前插入，为常见业务意图提供快速分类。
仅当置信度 > 0.85 时生效，否则降级到 LLM classify。
"""

import logging

import numpy as np

logger = logging.getLogger(__name__)

# ── Intent exemplars: representative queries for each intent ──
INTENT_EXEMPLARS: dict[str, list[str]] = {
    "leave_request": [
        "我想请假",
        "帮我请三天假",
        "年假还剩几天",
        "请假申请",
        "明天请一天事假",
        "我要休年假",
    ],
    "expense_claim": [
        "报销800块",
        "打车费报销",
        "出差费用报销",
        "提交报销单",
        "报销申请",
        "差旅费用",
    ],
    "approval": [
        "帮我审批",
        "待审批列表",
        "审批流程",
        "审批一下这个申请",
        "查看我的审批",
        "批准申请",
    ],
    "attendance": [
        "考勤记录",
        "打卡",
        "上班签到",
        "迟到记录",
        "出勤统计",
        "考勤异常",
    ],
    "sales_query": [
        "查看销售数据",
        "本月业绩怎么样",
        "销售漏斗",
        "成交额统计",
        "客户转化率",
        "销售目标完成情况",
    ],
    "crm_query": [
        "客户列表",
        "客户信息",
        "跟进客户",
        "添加新客户",
        "客户联系记录",
        "客户画像",
    ],
    "hr_query": [
        "员工花名册",
        "招聘进度",
        "绩效考核",
        "团队人员",
        "人事变动",
        "培训安排",
    ],
    "finance_query": [
        "财务报表",
        "预算查询",
        "资金流水",
        "成本分析",
        "利润统计",
        "应收账款",
    ],
    "project_query": [
        "项目进度",
        "任务分配",
        "项目列表",
        "里程碑",
        "甘特图",
        "项目统计",
    ],
    "calendar_query": [
        "今天有什么会议",
        "日程安排",
        "预约会议室",
        "本周日程",
        "创建日程",
        "会议安排",
    ],
    "knowledge_query": [
        "帮我查一下知识库",
        "搜索文档",
        "公司制度",
        "操作手册",
        "查找资料",
        "知识库搜索",
    ],
    "greeting": [
        "早上好",
        "你好",
        "在吗",
        "嗨",
        "下午好",
        "晚上好",
    ],
    "asset_query": [
        "固定资产查询",
        "资产盘点",
        "设备借用",
        "资产列表",
        "资产转移",
        "资产统计",
    ],
    "work_order": [
        "创建工单",
        "工单列表",
        "工单进度",
        "报修",
        "维修工单",
        "服务请求",
    ],
}

# Map intent keys to QueryComplexity values (imported lazily)
_INTENT_TO_COMPLEXITY: dict[str, str] = {
    "greeting": "simple",
    "leave_request": "moderate",
    "expense_claim": "moderate",
    "approval": "moderate",
    "attendance": "moderate",
    "sales_query": "moderate",
    "crm_query": "moderate",
    "hr_query": "moderate",
    "finance_query": "moderate",
    "project_query": "moderate",
    "calendar_query": "simple",
    "knowledge_query": "moderate",
    "asset_query": "moderate",
    "work_order": "moderate",
}

# Map intent keys to business domains (for tool filtering)
_INTENT_TO_DOMAINS: dict[str, list[str]] = {
    "leave_request": ["oa_leave"],
    "expense_claim": ["finance"],
    "approval": ["approval"],
    "attendance": ["attendance"],
    "sales_query": ["crm", "analytics"],
    "crm_query": ["crm"],
    "hr_query": ["hr"],
    "finance_query": ["finance"],
    "project_query": ["project"],
    "calendar_query": ["calendar"],
    "knowledge_query": ["knowledge"],
    "greeting": [],
    "asset_query": ["asset"],
    "work_order": ["oa_leave"],
}


class SemanticRouter:
    """Embedding-based intent classifier for fast routing."""

    def __init__(self):
        self._exemplar_embeddings: dict[str, list[np.ndarray]] | None = None
        self._initializing = False

    async def _ensure_initialized(self, org_id: str | None = None) -> bool:
        """Lazily compute and cache exemplar embeddings on first use."""
        if self._exemplar_embeddings is not None:
            return True
        if self._initializing:
            return False  # avoid re-entrant init

        self._initializing = True
        try:
            import asyncio

            from app.services.vector_service import vector_service

            # Collect all (intent, index, text) tuples for parallel embedding
            tasks: list[tuple[str, int, str]] = []
            for intent, exemplars in INTENT_EXEMPLARS.items():
                for idx, text in enumerate(exemplars):
                    tasks.append((intent, idx, text))

            # Fire all embedding calls in parallel (~84 calls, 1s vs 4-7s sequential)
            async def _embed(text: str) -> list[float] | None:
                return await vector_service.embed_text(text, org_id or "default")

            results = await asyncio.gather(*[_embed(t[2]) for t in tasks], return_exceptions=True)

            embeddings: dict[str, list[np.ndarray]] = {}
            for (intent, _, _), result in zip(tasks, results, strict=False):
                if isinstance(result, Exception) or result is None:
                    continue
                arr = np.array(result, dtype=np.float32)
                embeddings.setdefault(intent, []).append(arr)

            self._exemplar_embeddings = embeddings
            logger.info(
                f"[SemanticRouter] Initialized with {len(embeddings)} intents, "
                f"{sum(len(v) for v in embeddings.values())} exemplars"
            )
            return True
        except Exception as e:
            logger.warning(f"[SemanticRouter] Initialization failed: {e}")
            return False
        finally:
            self._initializing = False

    async def classify(self, query: str, org_id: str | None = None) -> tuple[str | None, float, list[str]]:
        """Classify query intent via embedding cosine similarity.

        Returns:
            (intent_key, confidence, domains) or (None, 0.0, []) if undetermined.
        """
        if not await self._ensure_initialized(org_id):
            return None, 0.0, []

        try:
            from app.services.vector_service import vector_service

            query_emb = await vector_service.embed_text(query, org_id or "default")
            if not query_emb:
                return None, 0.0, []

            query_vec = np.array(query_emb, dtype=np.float32)
            query_norm = np.linalg.norm(query_vec)
            if query_norm == 0:
                return None, 0.0, []

            best_intent: str | None = None
            best_score: float = 0.0

            for intent, emb_list in self._exemplar_embeddings.items():
                for emb in emb_list:
                    # Cosine similarity
                    score = float(np.dot(query_vec, emb) / (query_norm * np.linalg.norm(emb)))
                    if score > best_score:
                        best_score = score
                        best_intent = intent

            if best_intent and best_score > 0.85:
                domains = _INTENT_TO_DOMAINS.get(best_intent, [])
                logger.info(
                    f"[SemanticRouter] '{query[:30]}...' → {best_intent} "
                    f"(confidence={best_score:.3f}, domains={domains})"
                )
                return best_intent, best_score, domains

            return None, best_score, []

        except Exception as e:
            logger.error(f"[SemanticRouter] classify failed: {e}")
            return None, 0.0, []

    def get_complexity(self, intent: str) -> str:
        """Map intent key to complexity string."""
        return _INTENT_TO_COMPLEXITY.get(intent, "moderate")


# Singleton
semantic_router = SemanticRouter()
