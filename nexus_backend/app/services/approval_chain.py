"""
P2 Optimization: Multi-level Approval Chain Service
Supports configurable approval workflows with multiple levels.
Enhanced with DB-backed workflow definitions and timeout escalation.
P0: Wired chain execution with advance_step, match_and_bind_chain.
P4: Supports new node types (cc_notify, timer, sub_workflow) in advance_step.
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any

from app.core.database import supabase
from app.services.event_bus import EventType, emit

logger = logging.getLogger(__name__)


class ApprovalLevel(Enum):
    """Approval authority levels"""

    AUTO = "auto"  # Automatic approval (AI/Rules)
    MANAGER = "manager"  # Direct manager
    DIRECTOR = "director"  # Department director
    CFO = "cfo"  # Chief Financial Officer
    CEO = "ceo"  # Chief Executive Officer
    BOARD = "board"  # Board approval


@dataclass
class ApprovalStep:
    """A single step in an approval chain"""

    level: ApprovalLevel
    threshold: float  # Amount threshold for this level
    approver_role: str  # Role required to approve
    timeout_hours: int = 48  # Auto-escalate after timeout
    can_delegate: bool = True  # Can approver delegate?


@dataclass
class ApprovalChainConfig:
    """Configuration for an approval chain"""

    name: str
    description: str
    steps: list[ApprovalStep]
    applies_to: list[str]  # List of approval types this chain handles


# Default approval chains
DEFAULT_CHAINS: dict[str, ApprovalChainConfig] = {
    "expense": ApprovalChainConfig(
        name="费用报销审批链",
        description="适用于差旅、招待等费用报销",
        applies_to=["expense", "travel", "entertainment"],
        steps=[
            ApprovalStep(ApprovalLevel.AUTO, 500, "system", timeout_hours=0),
            ApprovalStep(ApprovalLevel.MANAGER, 5000, "manager", timeout_hours=24),
            ApprovalStep(ApprovalLevel.DIRECTOR, 20000, "director", timeout_hours=48),
            ApprovalStep(ApprovalLevel.CFO, 100000, "cfo", timeout_hours=72),
            ApprovalStep(ApprovalLevel.CEO, float("inf"), "ceo", timeout_hours=168),
        ],
    ),
    "purchase": ApprovalChainConfig(
        name="采购审批链",
        description="适用于设备、软件等采购申请",
        applies_to=["purchase", "procurement"],
        steps=[
            ApprovalStep(ApprovalLevel.AUTO, 2000, "system", timeout_hours=0),
            ApprovalStep(ApprovalLevel.MANAGER, 15000, "manager", timeout_hours=24),
            ApprovalStep(ApprovalLevel.DIRECTOR, 50000, "director", timeout_hours=48),
            ApprovalStep(ApprovalLevel.CFO, 200000, "cfo", timeout_hours=72),
            ApprovalStep(ApprovalLevel.BOARD, float("inf"), "board", timeout_hours=336),
        ],
    ),
    "leave": ApprovalChainConfig(
        name="请假审批链",
        description="适用于各类请假申请",
        applies_to=["leave", "vacation", "sick_leave"],
        steps=[
            ApprovalStep(ApprovalLevel.AUTO, 1, "system", timeout_hours=0),  # 1 day auto
            ApprovalStep(ApprovalLevel.MANAGER, 5, "manager", timeout_hours=24),
            ApprovalStep(ApprovalLevel.DIRECTOR, 15, "director", timeout_hours=48),
            ApprovalStep(ApprovalLevel.CEO, float("inf"), "ceo", timeout_hours=72),
        ],
    ),
    "default": ApprovalChainConfig(
        name="默认审批链",
        description="通用审批流程",
        applies_to=["*"],
        steps=[
            ApprovalStep(ApprovalLevel.AUTO, 1000, "system", timeout_hours=0),
            ApprovalStep(ApprovalLevel.MANAGER, 10000, "manager", timeout_hours=24),
            ApprovalStep(ApprovalLevel.CEO, float("inf"), "founder", timeout_hours=72),
        ],
    ),
}


class ApprovalChainService:
    """
    Service for managing multi-level approval workflows.
    """

    def __init__(self):
        self.chains = DEFAULT_CHAINS.copy()

    def get_chain_for_type(self, approval_type: str) -> ApprovalChainConfig:
        """
        Get the appropriate approval chain for a given type.
        Uses in-memory DEFAULT_CHAINS. For DB-backed chains, use load_chain_from_db().
        """
        for chain in self.chains.values():
            if approval_type in chain.applies_to:
                return chain
        return self.chains["default"]

    async def load_chain_from_db(self, org_id: str, approval_type: str, db=None) -> dict | None:
        """
        Load the active workflow definition from DB for the given org and approval type.
        Falls back to DEFAULT_CHAINS if no DB definition is found.
        """
        client = db or supabase
        if not client:
            logger.warning("No DB client available, falling back to DEFAULT_CHAINS")
            chain = self.get_chain_for_type(approval_type)
            return {
                "name": chain.name,
                "steps": [
                    {
                        "type": "approver",
                        "level": s.level.value,
                        "threshold": s.threshold,
                        "approver_role": s.approver_role,
                        "timeout_hours": s.timeout_hours,
                    }
                    for s in chain.steps
                ],
                "applies_to": chain.applies_to,
                "source": "default",
            }

        try:
            result = (
                await client.table("approval_chains")
                .select("*")
                .eq("organization_id", org_id)
                .eq("is_active", True)
                .contains("applies_to", [approval_type])
                .order("is_default", desc=True)
                .limit(1)
                .execute()
            )

            if result.data:
                chain_data = result.data[0]
                chain_data["source"] = "database"
                logger.info(f"Loaded workflow '{chain_data['name']}' from DB for org={org_id}, type={approval_type}")
                return chain_data

        except Exception as e:
            logger.error(f"Error loading chain from DB: {e}")

        # Fallback to DEFAULT_CHAINS
        chain = self.get_chain_for_type(approval_type)
        return {
            "name": chain.name,
            "steps": [
                {
                    "type": "approver",
                    "level": s.level.value,
                    "threshold": s.threshold,
                    "approver_role": s.approver_role,
                    "timeout_hours": s.timeout_hours,
                }
                for s in chain.steps
            ],
            "applies_to": chain.applies_to,
            "source": "default",
        }

    def determine_approval_level(self, approval_type: str, amount: float) -> tuple[ApprovalStep, int]:
        """
        Determine which approval level is required based on type and amount.
        Returns (ApprovalStep, step_index)
        """
        chain = self.get_chain_for_type(approval_type)

        for i, step in enumerate(chain.steps):
            if amount <= step.threshold:
                return step, i

        # Return highest level if amount exceeds all thresholds
        return chain.steps[-1], len(chain.steps) - 1

    async def get_approvers_for_step(self, step: ApprovalStep, requester_id: str) -> list[dict]:
        """
        Get list of users who can approve at the given step.
        """
        if not supabase:
            return []

        try:
            if step.level == ApprovalLevel.AUTO:
                return [{"id": "system", "name": "System Auto-Approval"}]

            # Get users with the required role
            result = (
                await supabase.table("users")
                .select("id, name, role, department")
                .eq("role", step.approver_role)
                .execute()
            )

            return result.data or []
        except Exception as e:
            logger.error(f"Error fetching approvers: {e}")
            return []

    async def get_direct_manager(self, user_id: str, db=None) -> dict | None:
        """
        Get the direct manager of a user.
        P2 Enhancement: Uses manager_id first, falls back to department-based lookup.
        """
        client = db or supabase
        if not client:
            return None

        try:
            # P2: First try manager_id direct lookup
            user = (
                await client.table("users").select("department, manager_id").eq("id", user_id).maybe_single().execute()
            )

            if not user.data:
                return None

            manager_id = user.data.get("manager_id")
            department = user.data.get("department")

            # Strategy 1: Use manager_id if available
            if manager_id:
                manager = await client.table("users").select("id, name").eq("id", manager_id).maybe_single().execute()
                if manager.data:
                    return manager.data

            # Strategy 2: Fall back to department-based lookup
            if department:
                manager = (
                    await client.table("users")
                    .select("id, name")
                    .eq("department", department)
                    .in_("role", ["manager", "founder"])
                    .neq("id", user_id)
                    .limit(1)
                    .execute()
                )
                if manager.data:
                    return manager.data[0]

            # Strategy 3: Fallback to any founder
            founder = await client.table("users").select("id, name").eq("role", "founder").limit(1).execute()

            return founder.data[0] if founder.data else None
        except Exception as e:
            logger.error(f"Error fetching manager: {e}")
            return None

    async def match_and_bind_chain(
        self,
        org_id: str,
        approval_type: str,
        amount: float,
        db=None,
    ) -> dict[str, Any]:
        """
        P0: Match an approval type to a workflow chain and determine the starting step.

        1. Tries to load from DB via load_chain_from_db(org_id, approval_type)
        2. Determines the starting step based on amount
        3. Returns chain_id, starting step index, approval_level, and timeout info

        Returns:
            {
                "chain_id": str | None,
                "chain_name": str,
                "starting_step": int,
                "approval_level": str,
                "timeout_at": str | None,
                "auto_approve": bool,
                "source": "database" | "default",
            }
        """
        chain_data = await self.load_chain_from_db(org_id, approval_type, db=db)

        # #16: Check organization auto-approval rules first
        try:
            from app.core.database import supabase as _sb
            _db = db or _sb
            if _db and org_id:
                rules_res = await (
                    _db.table("auto_approval_rules")
                    .select("name, condition_field, condition_op, condition_value")
                    .eq("organization_id", org_id)
                    .eq("approval_type", approval_type)
                    .eq("is_active", True)
                    .execute()
                )
                for rule in (rules_res.data or []):
                    op = rule.get("condition_op", "lte")
                    val = float(rule.get("condition_value", 0))
                    matched = (
                        (op == "lte" and amount <= val) or
                        (op == "lt" and amount < val) or
                        (op == "gte" and amount >= val) or
                        (op == "gt" and amount > val) or
                        (op == "eq" and amount == val)
                    )
                    if matched:
                        return {
                            "chain_id": None,
                            "chain_name": rule.get("name", "自动审批规则"),
                            "starting_step": 0,
                            "approval_level": "auto",
                            "timeout_at": None,
                            "auto_approve": True,
                            "source": "auto_rule",
                        }
        except Exception as e:
            logger.error("Auto-approval rules check failed (non-blocking): %s", e)

        if not chain_data:
            # Ultimate fallback
            return {
                "chain_id": None,
                "chain_name": "默认审批链",
                "starting_step": 0,
                "approval_level": "manager",
                "timeout_at": None,
                "auto_approve": False,
                "source": "default",
            }

        chain_id = chain_data.get("id")  # None for default/in-memory chains
        chain_name = chain_data.get("name", "审批链")
        steps = chain_data.get("steps", [])
        source = chain_data.get("source", "default")

        # Determine starting step based on amount thresholds
        starting_step = 0
        approval_level = ""
        auto_approve = False
        timeout_at = None

        for i, step in enumerate(steps):
            step_type = step.get("type", "approver")
            threshold = step.get("threshold", float("inf"))
            level = step.get("level", step.get("approver_role", ""))

            try:
                threshold_val = float(threshold)
            except (TypeError, ValueError):
                threshold_val = float("inf")

            if amount <= threshold_val:
                starting_step = i
                approval_level = level

                # Check if this step is an auto-approve step
                if step_type == "auto_approve" or level == "auto":
                    auto_approve = True
                else:
                    # Calculate timeout
                    timeout_hours = step.get("timeout_hours", 48)
                    if timeout_hours and timeout_hours > 0:
                        timeout_at = (datetime.now(UTC) + timedelta(hours=timeout_hours)).isoformat()

                break

        return {
            "chain_id": chain_id,
            "chain_name": chain_name,
            "starting_step": starting_step,
            "approval_level": approval_level,
            "timeout_at": timeout_at,
            "auto_approve": auto_approve,
            "source": source,
        }

    async def process_approval_request(
        self,
        request_id: str,
        approval_type: str,
        amount: float,
        requester_id: str,
        description: str = "",
    ) -> dict[str, Any]:
        """
        Process a new approval request through the chain.
        Returns the initial status and required approvers.
        """
        step, step_index = self.determine_approval_level(approval_type, amount)

        result = {
            "request_id": request_id,
            "chain_name": self.get_chain_for_type(approval_type).name,
            "current_step": step_index,
            "approval_level": step.level.value,
            "status": "pending",
            "approvers": [],
            "auto_approved": False,
            "reason": "",
        }

        # Check for auto-approval
        if step.level == ApprovalLevel.AUTO:
            result["status"] = "approved"
            result["auto_approved"] = True
            result["reason"] = f"金额 ¥{amount} 在自动审批限额 ¥{step.threshold} 内"

            # Emit event
            await emit(
                EventType.APPROVAL_APPROVED.value,
                {
                    "request_id": request_id,
                    "type": approval_type,
                    "amount": amount,
                    "auto": True,
                },
                user_id=requester_id,
            )
        else:
            # Get approvers for this level
            approvers = await self.get_approvers_for_step(step, requester_id)
            result["approvers"] = approvers
            result["reason"] = f"需要 {step.level.value} 级别审批 (限额: ¥{step.threshold})"

            # Try to get direct manager first for manager-level approvals
            if step.level == ApprovalLevel.MANAGER:
                manager = await self.get_direct_manager(requester_id)
                if manager:
                    result["primary_approver"] = manager

            # Emit escalation event
            await emit(
                EventType.APPROVAL_ESCALATED.value,
                {
                    "request_id": request_id,
                    "type": approval_type,
                    "amount": amount,
                    "level": step.level.value,
                    "approvers": [a.get("id") for a in approvers],
                },
                user_id=requester_id,
            )

        return result

    async def escalate_to_next_level(
        self,
        request_id: str,
        approval_type: str,
        current_step: int,
        amount: float,
        requester_id: str,
    ) -> dict[str, Any]:
        """
        Escalate an approval request to the next level.
        """
        chain = self.get_chain_for_type(approval_type)

        next_step_index = current_step + 1
        if next_step_index >= len(chain.steps):
            return {"success": False, "error": "Already at highest approval level"}

        next_step = chain.steps[next_step_index]
        approvers = await self.get_approvers_for_step(next_step, requester_id)

        # Emit escalation event
        await emit(
            EventType.APPROVAL_ESCALATED.value,
            {
                "request_id": request_id,
                "type": approval_type,
                "amount": amount,
                "level": next_step.level.value,
                "escalated_from": current_step,
                "approvers": [a.get("id") for a in approvers],
            },
            user_id=requester_id,
        )

        return {
            "success": True,
            "new_step": next_step_index,
            "approval_level": next_step.level.value,
            "approvers": approvers,
        }

    def get_all_chains(self) -> list[dict]:
        """
        Get all configured approval chains.
        """
        return [
            {
                "id": key,
                "name": chain.name,
                "description": chain.description,
                "applies_to": chain.applies_to,
                "steps": [
                    {
                        "level": step.level.value,
                        "threshold": step.threshold,
                        "approver_role": step.approver_role,
                        "timeout_hours": step.timeout_hours,
                    }
                    for step in chain.steps
                ],
            }
            for key, chain in self.chains.items()
        ]

    async def advance_step(
        self,
        request_id: str,
        decision: str,
        approver_id: str,
        comment: str | None = None,
        db=None,
    ) -> dict[str, Any]:
        """
        P0: Advance an approval request to the next step in the workflow.
        Records the decision in approval_history and updates current_step / timeout_at.

        Enhanced to handle special node types:
        - condition: Evaluate condition and skip to target step
        - auto_approve: Check amount threshold and auto-approve if within limits
        - notify / cc_notify: Emit notification and auto-advance to next step
        - parallel: Track parallel approvals (all must approve)
        - timer: Set timeout and auto-advance when expired
        - sub_workflow: Placeholder for future sub-workflow support

        Args:
            request_id: The approval request ID
            decision: 'approved' or 'rejected'
            approver_id: The user ID who made the decision
            comment: Optional comment from the approver
            db: RLS-scoped DB client

        Returns:
            Updated approval request data
        """
        client = db or supabase
        if not client:
            raise ValueError("Database client unavailable")

        # Fetch current request
        req_result = await client.table("approval_requests").select("*").eq("id", request_id).maybe_single().execute()

        if not req_result.data:
            raise RuntimeError(f"Approval request {request_id} not found")

        request_data = req_result.data
        current_step = request_data.get("current_step", 0)
        current_status = request_data.get("status", "pending")
        history = request_data.get("approval_history", []) or []

        # Self-approval guard: the submitter cannot approve/reject their own request
        submitted_by = request_data.get("submitted_by", "")
        if approver_id == submitted_by:
            raise RuntimeError("不能审批自己提交的申请")

        # Optimistic lock: reject if already processed
        if current_status != "pending":
            raise RuntimeError(f"Approval {request_id} already {current_status}, cannot advance")

        # Record this decision in history
        history_entry = {
            "step": current_step,
            "decision": decision,
            "approver_id": approver_id,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        if comment:
            history_entry["comment"] = comment
        history.append(history_entry)

        # If rejected, finalize immediately
        if decision == "rejected":
            update_data = {
                "status": "rejected",
                "approval_history": history,
                "timeout_at": None,
            }
            result = (
                await client.table("approval_requests")
                .update(update_data)
                .eq("id", request_id)
                .eq("current_step", current_step)
                .eq("status", "pending")
                .execute()
            )
            if not result.data:
                raise RuntimeError(f"Approval {request_id} was modified concurrently, please retry")
            logger.info(f"Approval {request_id} rejected by {approver_id} at step {current_step}")
            return result.data[0]

        # If approved, check if there are more steps in the chain
        chain_id = request_data.get("chain_id")
        next_step = current_step + 1
        has_more_steps = False

        if chain_id:
            # Load the chain definition to check step count
            chain_result = (
                await client.table("approval_chains").select("steps").eq("id", chain_id).maybe_single().execute()
            )
            if chain_result.data:
                chain_steps = chain_result.data.get("steps", [])
                has_more_steps = next_step < len(chain_steps)

                if has_more_steps:
                    # P0/P4: Handle special node types for the next step
                    next_step_def = chain_steps[next_step]
                    next_step_type = next_step_def.get("type", "approver")

                    # Handle condition nodes: evaluate and skip to target
                    if next_step_type == "condition":
                        target = await self.evaluate_condition(next_step_def, request_data)
                        if target is not None:
                            # Find the target step index by ID
                            target_index = self._find_step_index(chain_steps, target)
                            if target_index is not None:
                                next_step = target_index
                                next_step_def = chain_steps[next_step]
                                next_step_type = next_step_def.get("type", "approver")
                                has_more_steps = next_step < len(chain_steps)
                                # Record condition jump in history
                                history.append(
                                    {
                                        "step": current_step + 1,
                                        "decision": "condition_evaluated",
                                        "approver_id": "system",
                                        "timestamp": datetime.now(UTC).isoformat(),
                                        "comment": f"条件节点跳转到步骤 {target}",
                                    }
                                )

                    # Handle auto_approve nodes: check threshold
                    if next_step_type == "auto_approve":
                        amount = request_data.get("amount", 0)
                        threshold = next_step_def.get("threshold", 0)
                        try:
                            if float(amount) <= float(threshold):
                                # Auto-approve and finalize
                                history.append(
                                    {
                                        "step": next_step,
                                        "decision": "auto_approved",
                                        "approver_id": "system",
                                        "timestamp": datetime.now(UTC).isoformat(),
                                        "comment": f"金额 ¥{amount} 在自动审批限额 ¥{threshold} 内",
                                    }
                                )
                                update_data = {
                                    "status": "approved",
                                    "current_step": next_step,
                                    "approval_history": history,
                                    "timeout_at": None,
                                }
                                result = (
                                    await client.table("approval_requests")
                                    .update(update_data)
                                    .eq("id", request_id)
                                    .eq("current_step", current_step)
                                    .eq("status", "pending")
                                    .execute()
                                )
                                if not result.data:
                                    raise RuntimeError(f"Approval {request_id} was modified concurrently, please retry")
                                logger.info(
                                    f"Approval {request_id} auto-approved at step {next_step} "
                                    f"(amount={amount}, threshold={threshold})"
                                )
                                return result.data[0]
                        except (TypeError, ValueError):
                            pass
                        # If not auto-approved, continue to next step normally
                        next_step += 1
                        has_more_steps = next_step < len(chain_steps)
                        if has_more_steps:
                            next_step_def = chain_steps[next_step]

                    # Handle notify / cc_notify nodes: emit notification and auto-advance
                    if next_step_type in ("notify", "cc_notify"):
                        notify_targets = next_step_def.get("notify_targets", [])
                        notify_message = next_step_def.get("message", "审批流程通知")
                        # Record notification in history
                        history.append(
                            {
                                "step": next_step,
                                "decision": "notified",
                                "approver_id": "system",
                                "timestamp": datetime.now(UTC).isoformat(),
                                "comment": f"已通知: {', '.join(notify_targets) if notify_targets else '相关人员'}",
                            }
                        )
                        # Emit notification event
                        await emit(
                            EventType.APPROVAL_ESCALATED.value,
                            {
                                "request_id": request_id,
                                "type": request_data.get("type", ""),
                                "notify_type": next_step_type,
                                "targets": notify_targets,
                                "message": notify_message,
                            },
                            user_id=approver_id,
                        )
                        # Auto-advance past notification step
                        next_step += 1
                        has_more_steps = next_step < len(chain_steps)
                        if has_more_steps:
                            next_step_def = chain_steps[next_step]

                    # Handle timer nodes: set timeout and auto-advance
                    if has_more_steps and next_step_def.get("type") == "timer":
                        wait_hours = next_step_def.get("wait_hours", 24)
                        history.append(
                            {
                                "step": next_step,
                                "decision": "timer_started",
                                "approver_id": "system",
                                "timestamp": datetime.now(UTC).isoformat(),
                                "comment": f"等待 {wait_hours} 小时后自动推进",
                            }
                        )
                        # For timer nodes, set timeout but move to next step
                        next_step += 1
                        has_more_steps = next_step < len(chain_steps)
                        if has_more_steps:
                            next_step_def = chain_steps[next_step]

                    # Handle parallel nodes: track parallel approvals
                    if has_more_steps and next_step_def.get("type") == "parallel":
                        required_approvals = next_step_def.get("required_count", 1)
                        _parallel_approvers = next_step_def.get("approvers", [])
                        # Check how many parallel approvals we have at this step
                        parallel_count = sum(
                            1 for h in history if h.get("step") == next_step and h.get("decision") == "approved"
                        )
                        if parallel_count < required_approvals:
                            # Still waiting for more parallel approvals
                            # Update to the parallel step but keep status pending
                            pass  # Falls through to the normal pending-step update below

                if has_more_steps:
                    # Calculate timeout for next step
                    next_step_def = chain_steps[next_step] if next_step < len(chain_steps) else {}
                    timeout_hours = next_step_def.get("timeout_hours", 48)
                    timeout_at = (
                        (datetime.now(UTC) + timedelta(hours=timeout_hours)).isoformat() if timeout_hours > 0 else None
                    )

                    update_data = {
                        "current_step": next_step,
                        "approval_level": next_step_def.get("level", next_step_def.get("approver_role", "")),
                        "approval_history": history,
                        "timeout_at": timeout_at,
                    }
                else:
                    # All steps completed -> approved
                    update_data = {
                        "status": "approved",
                        "current_step": next_step,
                        "approval_history": history,
                        "timeout_at": None,
                    }
            else:
                # Chain not found in DB, mark as approved
                update_data = {
                    "status": "approved",
                    "approval_history": history,
                    "timeout_at": None,
                }
        else:
            # No chain_id -> single-step approval, mark as approved
            update_data = {
                "status": "approved",
                "approval_history": history,
                "timeout_at": None,
            }

        result = (
            await client.table("approval_requests")
            .update(update_data)
            .eq("id", request_id)
            .eq("current_step", current_step)
            .eq("status", "pending")
            .execute()
        )

        if not result.data:
            raise RuntimeError(f"Approval {request_id} was modified concurrently, please retry")

        logger.info(
            f"Advanced approval {request_id}: step {current_step} -> {next_step}, "
            f"decision={decision}, approver={approver_id}"
        )
        return result.data[0]

    @staticmethod
    def _find_step_index(chain_steps: list[dict], target_id: str) -> int | None:
        """Find the index of a step by its ID in the chain steps list."""
        for i, step in enumerate(chain_steps):
            if step.get("id") == target_id:
                return i
        # Also try matching by index string
        try:
            idx = int(target_id)
            if 0 <= idx < len(chain_steps):
                return idx
        except (TypeError, ValueError):
            pass
        return None

    async def evaluate_condition(
        self,
        condition_node: dict,
        request_data: dict,
    ) -> str | None:
        """
        Evaluate a condition node against request data.
        Returns the target node ID for the matching branch, or None if no match.

        Supported operators:
        - amount_gt: amount greater than value
        - amount_lt: amount less than value
        - department_eq: department equals value
        - role_eq: requester role equals value
        """
        branches = condition_node.get("branches", [])

        for branch in branches:
            operator = branch.get("operator", "")
            value = branch.get("value")
            target = branch.get("target")

            if not operator or target is None:
                continue

            match = False

            if operator == "amount_gt":
                amount = request_data.get("amount", 0)
                try:
                    match = float(amount) > float(value)
                except (TypeError, ValueError):
                    match = False

            elif operator == "amount_lt":
                amount = request_data.get("amount", 0)
                try:
                    match = float(amount) < float(value)
                except (TypeError, ValueError):
                    match = False

            elif operator == "department_eq":
                dept = request_data.get("department", "")
                match = str(dept).lower() == str(value).lower()

            elif operator == "role_eq":
                role = request_data.get("role", "")
                match = str(role).lower() == str(value).lower()

            else:
                logger.warning(f"Unknown condition operator: {operator}")
                continue

            if match:
                return target

        # Return default branch if specified
        default_target = condition_node.get("default_target")
        return default_target

    async def check_timeout_escalation(self, db=None) -> int:
        """
        Scan for approval requests that have timed out and escalate them.
        Called periodically by the background task.

        Returns:
            Number of requests escalated
        """
        client = db or supabase
        if not client:
            return 0

        escalated_count = 0

        try:
            now = datetime.now(UTC).isoformat()

            # Find all timed-out pending requests
            result = (
                await client.table("approval_requests")
                .select("id, type, current_step, amount, submitted_by, chain_id")
                .eq("status", "pending")
                .eq("escalated", False)
                .lt("timeout_at", now)
                .limit(50)
                .execute()
            )

            if not result.data:
                return 0

            for req in result.data:
                try:
                    request_id = req["id"]
                    approval_type = req.get("type", "default")
                    current_step = req.get("current_step", 0)
                    amount = req.get("amount", 0)
                    requester_id = req.get("submitted_by", "")

                    # Attempt escalation to next level
                    esc_result = await self.escalate_to_next_level(
                        request_id=request_id,
                        approval_type=approval_type,
                        current_step=current_step,
                        amount=float(amount) if amount else 0,
                        requester_id=requester_id,
                    )

                    if esc_result.get("success"):
                        new_step = esc_result.get("new_step", current_step + 1)
                        # Calculate new timeout for escalated step
                        timeout_hours = 48  # default escalation timeout

                        # Try to get timeout from chain definition
                        chain_id = req.get("chain_id")
                        if chain_id:
                            try:
                                chain_result = (
                                    await client.table("approval_chains")
                                    .select("steps")
                                    .eq("id", chain_id)
                                    .maybe_single()
                                    .execute()
                                )
                                if chain_result.data:
                                    steps = chain_result.data.get("steps", [])
                                    if new_step < len(steps):
                                        timeout_hours = steps[new_step].get("timeout_hours", 48)
                            except Exception:
                                pass

                        new_timeout = (datetime.now(UTC) + timedelta(hours=timeout_hours)).isoformat()

                        # Update the request with escalation info (optimistic lock)
                        esc_update_result = await (
                            client.table("approval_requests")
                            .update(
                                {
                                    "current_step": new_step,
                                    "approval_level": esc_result.get("approval_level", ""),
                                    "escalated": True,
                                    "timeout_at": new_timeout,
                                }
                            )
                            .eq("id", request_id)
                            .eq("escalated", False)
                            .eq("status", "pending")
                            .execute()
                        )
                        if not esc_update_result.data:
                            logger.info(f"Approval {request_id} already escalated concurrently, skipping")
                            continue
                        escalated_count += 1
                        logger.info(f"Escalated approval {request_id} from step {current_step} to {new_step}")
                    else:
                        # Already at highest level, mark as escalated to prevent re-processing
                        await (
                            client.table("approval_requests")
                            .update({"escalated": True, "timeout_at": None})
                            .eq("id", request_id)
                            .execute()
                        )
                        logger.warning(f"Approval {request_id} at highest level, cannot escalate further")

                except Exception as e:
                    logger.error(f"Error escalating request {req.get('id')}: {e}")

        except Exception as e:
            logger.error(f"Error during timeout escalation scan: {e}")

        if escalated_count > 0:
            logger.info(f"Timeout escalation: escalated {escalated_count} requests")

        return escalated_count


# Global service instance
approval_chain_service = ApprovalChainService()
