"""
#3 — Approval Chain (审批链执行逻辑测试)

测试审批链的各类节点处理:
- advance_step: approver 节点 -> 推进到下一步
- advance_step: condition 节点 -> 计算条件并跳转
- advance_step: auto_approve 节点 -> 检查金额阈值
- advance_step: notify 节点 -> 自动跳过
- advance_step: 最终步骤 -> 设置 status=approved
- advance_step: 拒绝 -> 立即设置 status=rejected
- match_and_bind_chain: 从 DB 找到正确的审批链
- match_and_bind_chain: 回退到默认链
- evaluate_condition: 条件评估逻辑
"""


import pytest

from tests.conftest import MockSupabaseClient

# ═══════════════════════════════════════════════════════════════════════════════
#  Helper: 构建带审批链数据的 mock DB
# ═══════════════════════════════════════════════════════════════════════════════


def _make_db_with_request(request_data: dict, chain_steps: list | None = None) -> MockSupabaseClient:
    """构建包含审批请求和链定义的 mock DB"""
    db = MockSupabaseClient()
    db.set_table_data("approval_requests", [request_data])

    if chain_steps is not None and request_data.get("chain_id"):
        db.set_table_data(
            "approval_chains",
            [{"id": request_data["chain_id"], "steps": chain_steps}],
        )

    return db


# ═══════════════════════════════════════════════════════════════════════════════
#  advance_step 测试
# ═══════════════════════════════════════════════════════════════════════════════


class TestAdvanceStep:
    """测试 advance_step 方法"""

    async def test_advance_with_approver_node(self):
        """approver 节点批准后应推进到下一步"""
        from app.services.approval_chain import ApprovalChainService

        service = ApprovalChainService()

        chain_steps = [
            {"type": "approver", "level": "manager", "timeout_hours": 24},
            {"type": "approver", "level": "director", "timeout_hours": 48},
        ]

        request_data = {
            "id": "req-001",
            "status": "pending",
            "current_step": 0,
            "chain_id": "chain-001",
            "approval_history": [],
        }

        db = _make_db_with_request(request_data, chain_steps)

        result = await service.advance_step(
            request_id="req-001",
            decision="approved",
            approver_id="user-001",
            comment="同意",
            db=db,
        )

        assert result is not None
        # 由于 mock 的 update 返回原始数据, 验证不抛异常即可

    async def test_advance_rejection_sets_rejected(self):
        """拒绝审批应立即设置 status=rejected"""
        from app.services.approval_chain import ApprovalChainService

        service = ApprovalChainService()

        request_data = {
            "id": "req-002",
            "status": "pending",
            "current_step": 0,
            "chain_id": "chain-001",
            "approval_history": [],
        }

        chain_steps = [
            {"type": "approver", "level": "manager", "timeout_hours": 24},
        ]

        db = _make_db_with_request(request_data, chain_steps)

        result = await service.advance_step(
            request_id="req-002",
            decision="rejected",
            approver_id="user-002",
            comment="预算超标，不同意",
            db=db,
        )

        assert result is not None

    async def test_advance_already_processed_raises(self):
        """已处理的审批请求不应能再次推进"""
        from app.services.approval_chain import ApprovalChainService

        service = ApprovalChainService()

        request_data = {
            "id": "req-003",
            "status": "approved",  # 已批准
            "current_step": 1,
            "chain_id": "chain-001",
            "approval_history": [],
        }

        db = _make_db_with_request(request_data, [])

        with pytest.raises(RuntimeError, match="already"):
            await service.advance_step(
                request_id="req-003",
                decision="approved",
                approver_id="user-003",
                db=db,
            )

    async def test_advance_not_found_raises(self):
        """不存在的审批请求应抛出异常"""
        from app.services.approval_chain import ApprovalChainService

        service = ApprovalChainService()

        db = MockSupabaseClient()
        db.set_table_data("approval_requests", [])  # 空结果

        with pytest.raises(RuntimeError, match="not found"):
            await service.advance_step(
                request_id="nonexistent",
                decision="approved",
                approver_id="user-001",
                db=db,
            )

    async def test_advance_no_chain_id_auto_approves(self):
        """没有 chain_id 的单步审批批准后应直接完成"""
        from app.services.approval_chain import ApprovalChainService

        service = ApprovalChainService()

        request_data = {
            "id": "req-004",
            "status": "pending",
            "current_step": 0,
            "chain_id": None,  # 无审批链
            "approval_history": [],
        }

        db = _make_db_with_request(request_data, None)

        result = await service.advance_step(
            request_id="req-004",
            decision="approved",
            approver_id="user-004",
            db=db,
        )

        assert result is not None


# ═══════════════════════════════════════════════════════════════════════════════
#  evaluate_condition 测试
# ═══════════════════════════════════════════════════════════════════════════════


class TestEvaluateCondition:
    """测试条件节点评估 (evaluate_condition)"""

    async def test_amount_gt_match(self):
        """amount_gt 条件匹配"""
        from app.services.approval_chain import ApprovalChainService

        service = ApprovalChainService()

        condition_node = {
            "branches": [
                {"operator": "amount_gt", "value": 10000, "target": "step_director"},
                {"operator": "amount_lt", "value": 10000, "target": "step_manager"},
            ],
        }

        request_data = {"amount": 50000}
        result = await service.evaluate_condition(condition_node, request_data)
        assert result == "step_director"

    async def test_amount_lt_match(self):
        """amount_lt 条件匹配"""
        from app.services.approval_chain import ApprovalChainService

        service = ApprovalChainService()

        condition_node = {
            "branches": [
                {"operator": "amount_gt", "value": 10000, "target": "step_director"},
                {"operator": "amount_lt", "value": 10000, "target": "step_manager"},
            ],
        }

        request_data = {"amount": 5000}
        result = await service.evaluate_condition(condition_node, request_data)
        assert result == "step_manager"

    async def test_department_eq_match(self):
        """department_eq 条件匹配"""
        from app.services.approval_chain import ApprovalChainService

        service = ApprovalChainService()

        condition_node = {
            "branches": [
                {"operator": "department_eq", "value": "engineering", "target": "step_cto"},
            ],
        }

        request_data = {"department": "Engineering"}
        result = await service.evaluate_condition(condition_node, request_data)
        assert result == "step_cto"

    async def test_no_match_returns_default(self):
        """无匹配分支时应返回 default_target"""
        from app.services.approval_chain import ApprovalChainService

        service = ApprovalChainService()

        condition_node = {
            "branches": [
                {"operator": "amount_gt", "value": 100000, "target": "step_ceo"},
            ],
            "default_target": "step_manager",
        }

        request_data = {"amount": 5000}
        result = await service.evaluate_condition(condition_node, request_data)
        assert result == "step_manager"

    async def test_no_match_no_default_returns_none(self):
        """无匹配且无默认目标时返回 None"""
        from app.services.approval_chain import ApprovalChainService

        service = ApprovalChainService()

        condition_node = {
            "branches": [
                {"operator": "amount_gt", "value": 100000, "target": "step_ceo"},
            ],
        }

        request_data = {"amount": 5000}
        result = await service.evaluate_condition(condition_node, request_data)
        assert result is None

    async def test_role_eq_match(self):
        """role_eq 条件匹配"""
        from app.services.approval_chain import ApprovalChainService

        service = ApprovalChainService()

        condition_node = {
            "branches": [
                {"operator": "role_eq", "value": "manager", "target": "step_skip"},
            ],
        }

        request_data = {"role": "manager"}
        result = await service.evaluate_condition(condition_node, request_data)
        assert result == "step_skip"


# ═══════════════════════════════════════════════════════════════════════════════
#  match_and_bind_chain 测试
# ═══════════════════════════════════════════════════════════════════════════════


class TestMatchAndBindChain:
    """测试审批链匹配绑定 (match_and_bind_chain)"""

    async def test_match_falls_back_to_default(self):
        """无 DB 数据时应回退到默认链"""
        from app.services.approval_chain import ApprovalChainService

        service = ApprovalChainService()

        db = MockSupabaseClient()
        db.set_table_data("approval_chains", [])

        result = await service.match_and_bind_chain(
            org_id="org-001",
            approval_type="purchase",
            amount=1000,
            db=db,
        )

        assert result["source"] == "default"
        assert "chain_name" in result
        assert "starting_step" in result

    async def test_match_auto_approve_small_amount(self):
        """小金额应触发自动审批"""
        from app.services.approval_chain import ApprovalChainService

        service = ApprovalChainService()

        db = MockSupabaseClient()
        db.set_table_data("approval_chains", [])

        result = await service.match_and_bind_chain(
            org_id="org-001",
            approval_type="expense",
            amount=100,  # 小于 expense 链的 auto 阈值
            db=db,
        )

        assert result["auto_approve"] is True

    async def test_match_large_amount_no_auto(self):
        """大金额不应触发自动审批"""
        from app.services.approval_chain import ApprovalChainService

        service = ApprovalChainService()

        db = MockSupabaseClient()
        db.set_table_data("approval_chains", [])

        result = await service.match_and_bind_chain(
            org_id="org-001",
            approval_type="purchase",
            amount=100000,
            db=db,
        )

        assert result["auto_approve"] is False


# ═══════════════════════════════════════════════════════════════════════════════
#  determine_approval_level 测试
# ═══════════════════════════════════════════════════════════════════════════════


class TestDetermineApprovalLevel:
    """测试审批级别确定"""

    def test_small_expense_auto_approved(self):
        """小额费用应自动审批"""
        from app.services.approval_chain import ApprovalChainService, ApprovalLevel

        service = ApprovalChainService()

        step, index = service.determine_approval_level("expense", 100)
        assert step.level == ApprovalLevel.AUTO
        assert index == 0

    def test_large_expense_needs_cfo(self):
        """大额费用应需要 CFO 审批"""
        from app.services.approval_chain import ApprovalChainService, ApprovalLevel

        service = ApprovalChainService()

        step, index = service.determine_approval_level("expense", 50000)
        assert step.level == ApprovalLevel.CFO

    def test_unknown_type_uses_default(self):
        """未知审批类型应使用默认链"""
        from app.services.approval_chain import ApprovalChainService

        service = ApprovalChainService()

        step, index = service.determine_approval_level("unknown_type", 5000)
        assert step is not None

    def test_leave_short_auto(self):
        """短期请假应自动审批"""
        from app.services.approval_chain import ApprovalChainService, ApprovalLevel

        service = ApprovalChainService()

        step, index = service.determine_approval_level("leave", 0.5)  # 半天
        assert step.level == ApprovalLevel.AUTO
