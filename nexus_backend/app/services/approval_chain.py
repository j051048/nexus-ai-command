"""
P2 Optimization: Multi-level Approval Chain Service
Supports configurable approval workflows with multiple levels.
"""
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum
from app.core.database import supabase
from app.services.event_bus import emit, EventType


class ApprovalLevel(Enum):
    """Approval authority levels"""
    AUTO = "auto"           # Automatic approval (AI/Rules)
    MANAGER = "manager"     # Direct manager
    DIRECTOR = "director"   # Department director
    CFO = "cfo"             # Chief Financial Officer
    CEO = "ceo"             # Chief Executive Officer
    BOARD = "board"         # Board approval


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
    steps: List[ApprovalStep]
    applies_to: List[str]  # List of approval types this chain handles


# Default approval chains
DEFAULT_CHAINS: Dict[str, ApprovalChainConfig] = {
    "expense": ApprovalChainConfig(
        name="费用报销审批链",
        description="适用于差旅、招待等费用报销",
        applies_to=["expense", "travel", "entertainment"],
        steps=[
            ApprovalStep(ApprovalLevel.AUTO, 500, "system", timeout_hours=0),
            ApprovalStep(ApprovalLevel.MANAGER, 5000, "manager", timeout_hours=24),
            ApprovalStep(ApprovalLevel.DIRECTOR, 20000, "director", timeout_hours=48),
            ApprovalStep(ApprovalLevel.CFO, 100000, "cfo", timeout_hours=72),
            ApprovalStep(ApprovalLevel.CEO, float('inf'), "ceo", timeout_hours=168),
        ]
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
            ApprovalStep(ApprovalLevel.BOARD, float('inf'), "board", timeout_hours=336),
        ]
    ),
    "leave": ApprovalChainConfig(
        name="请假审批链",
        description="适用于各类请假申请",
        applies_to=["leave", "vacation", "sick_leave"],
        steps=[
            ApprovalStep(ApprovalLevel.AUTO, 1, "system", timeout_hours=0),  # 1 day auto
            ApprovalStep(ApprovalLevel.MANAGER, 5, "manager", timeout_hours=24),
            ApprovalStep(ApprovalLevel.DIRECTOR, 15, "director", timeout_hours=48),
            ApprovalStep(ApprovalLevel.CEO, float('inf'), "ceo", timeout_hours=72),
        ]
    ),
    "default": ApprovalChainConfig(
        name="默认审批链",
        description="通用审批流程",
        applies_to=["*"],
        steps=[
            ApprovalStep(ApprovalLevel.AUTO, 1000, "system", timeout_hours=0),
            ApprovalStep(ApprovalLevel.MANAGER, 10000, "manager", timeout_hours=24),
            ApprovalStep(ApprovalLevel.CEO, float('inf'), "founder", timeout_hours=72),
        ]
    )
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
        """
        for chain in self.chains.values():
            if approval_type in chain.applies_to:
                return chain
        return self.chains["default"]
    
    def determine_approval_level(
        self, 
        approval_type: str, 
        amount: float
    ) -> tuple[ApprovalStep, int]:
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
    
    async def get_approvers_for_step(
        self, 
        step: ApprovalStep, 
        requester_id: str
    ) -> List[Dict]:
        """
        Get list of users who can approve at the given step.
        """
        if not supabase:
            return []
        
        try:
            if step.level == ApprovalLevel.AUTO:
                return [{"id": "system", "name": "System Auto-Approval"}]
            
            # Get users with the required role
            result = await supabase.table("users")\
                .select("id, name, role, department")\
                .eq("role", step.approver_role)\
                .execute()
            
            return result.data or []
        except Exception as e:
            print(f"Error fetching approvers: {e}")
            return []
    
    async def get_direct_manager(self, user_id: str) -> Optional[Dict]:
        """
        Get the direct manager of a user.
        """
        if not supabase:
            return None
        
        try:
            # Get user's department
            user = await supabase.table("users")\
                .select("department")\
                .eq("id", user_id)\
                .maybe_single()\
                .execute()
            
            if not user.data:
                return None
            
            department = user.data.get("department")
            
            # Find manager in same department (simplified logic)
            # In a real system, you'd have a manager_id field or org structure
            manager = await supabase.table("users")\
                .select("id, name")\
                .eq("department", department)\
                .in_("role", ["manager", "founder"])\
                .neq("id", user_id)\
                .limit(1)\
                .execute()
            
            if manager.data:
                return manager.data[0]
            
            # Fallback to any founder
            founder = await supabase.table("users")\
                .select("id, name")\
                .eq("role", "founder")\
                .limit(1)\
                .execute()
            
            return founder.data[0] if founder.data else None
        except Exception as e:
            print(f"Error fetching manager: {e}")
            return None
    
    async def process_approval_request(
        self,
        request_id: str,
        approval_type: str,
        amount: float,
        requester_id: str,
        description: str = ""
    ) -> Dict[str, Any]:
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
            "reason": ""
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
                    "auto": True
                },
                user_id=requester_id
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
                    "approvers": [a.get("id") for a in approvers]
                },
                user_id=requester_id
            )
        
        return result
    
    async def escalate_to_next_level(
        self,
        request_id: str,
        approval_type: str,
        current_step: int,
        amount: float,
        requester_id: str
    ) -> Dict[str, Any]:
        """
        Escalate an approval request to the next level.
        """
        chain = self.get_chain_for_type(approval_type)
        
        next_step_index = current_step + 1
        if next_step_index >= len(chain.steps):
            return {
                "success": False,
                "error": "Already at highest approval level"
            }
        
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
                "approvers": [a.get("id") for a in approvers]
            },
            user_id=requester_id
        )
        
        return {
            "success": True,
            "new_step": next_step_index,
            "approval_level": next_step.level.value,
            "approvers": approvers
        }
    
    def get_all_chains(self) -> List[Dict]:
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
                        "timeout_hours": step.timeout_hours
                    }
                    for step in chain.steps
                ]
            }
            for key, chain in self.chains.items()
        ]


# Global service instance
approval_chain_service = ApprovalChainService()