"""Simple AI execution policy and orchestration governance APIs."""

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from app.core.auth import get_current_org_id, get_current_user_id
from app.core.dependencies import get_request_db, require_role
from app.core.errors import api_success
from app.services.ai_execution_policy_service import (
    AIExecutionMode,
    AIExecutionPolicy,
    SimulationCase,
    ai_execution_policy_service,
    worker_registry,
)

router = APIRouter()
require_policy_admin = require_role(["admin", "founder", "boss"])


class PolicyUpdateRequest(BaseModel):
    mode: AIExecutionMode
    max_task_cost_usd: float | None = Field(default=None, ge=0.001, le=5.0)
    max_input_tokens: int | None = Field(default=None, ge=1_000, le=128_000)
    max_output_tokens: int | None = Field(default=None, ge=256, le=16_384)
    max_latency_ms: int | None = Field(default=None, ge=5_000, le=180_000)
    retain_inference_receipts: bool | None = None
    high_risk_terms: list[str] | None = Field(default=None, max_length=50)
    medium_risk_terms: list[str] | None = Field(default=None, max_length=50)

    def to_policy(self, current: AIExecutionPolicy) -> AIExecutionPolicy:
        policy = AIExecutionPolicy.for_mode(self.mode)
        policy.premium_model = current.premium_model
        if self.max_task_cost_usd is not None:
            policy.max_task_cost_usd = self.max_task_cost_usd
        if self.max_input_tokens is not None:
            policy.max_input_tokens = self.max_input_tokens
        if self.max_output_tokens is not None:
            policy.max_output_tokens = self.max_output_tokens
        if self.max_latency_ms is not None:
            policy.max_latency_ms = self.max_latency_ms
        policy.retain_inference_receipts = (
            self.retain_inference_receipts
            if self.retain_inference_receipts is not None
            else current.retain_inference_receipts
        )
        policy.high_risk_terms = (
            self.high_risk_terms
            if self.high_risk_terms is not None
            else current.high_risk_terms
        )
        policy.medium_risk_terms = (
            self.medium_risk_terms
            if self.medium_risk_terms is not None
            else current.medium_risk_terms
        )
        return policy


class PolicySimulationRequest(BaseModel):
    cases: list[SimulationCase] = Field(min_length=1, max_length=100)


@router.get("/policy")
async def get_policy(
    org_id: str = Depends(get_current_org_id),
    _user_id: str = Depends(get_current_user_id),
    db=Depends(get_request_db),
):
    policy = await ai_execution_policy_service.get_policy(org_id, db=db)
    return api_success(
        {
            "policy": policy.model_dump(mode="json"),
            "presets": {
                mode.value: AIExecutionPolicy.for_mode(mode).model_dump(mode="json")
                for mode in AIExecutionMode
            },
        }
    )


@router.put("/policy")
async def update_policy(
    body: PolicyUpdateRequest,
    org_id: str = Depends(get_current_org_id),
    _admin_id: str = Depends(require_policy_admin),
    db=Depends(get_request_db),
):
    current = await ai_execution_policy_service.get_policy(org_id, db=db)
    policy = await ai_execution_policy_service.save_policy(
        org_id, body.to_policy(current), db
    )
    return api_success(policy.model_dump(mode="json"), message="AI 执行策略已更新")


@router.get("/policy/workers")
async def list_policy_workers(
    org_id: str = Depends(get_current_org_id),
    _user_id: str = Depends(get_current_user_id),
    db=Depends(get_request_db),
):
    policy = await ai_execution_policy_service.get_policy(org_id, db=db)
    return api_success(
        [worker.model_dump(mode="json") for worker in worker_registry(policy)]
    )


@router.post("/policy/simulate")
async def simulate_policy(
    body: PolicySimulationRequest,
    org_id: str = Depends(get_current_org_id),
    _admin_id: str = Depends(require_policy_admin),
    db=Depends(get_request_db),
):
    policy = await ai_execution_policy_service.get_policy(org_id, db=db)
    results = await ai_execution_policy_service.simulate(body.cases, policy)
    return api_success([item.model_dump(mode="json") for item in results])


@router.get("/service-overview")
async def get_service_overview(
    request: Request,
    org_id: str = Depends(get_current_org_id),
    _user_id: str = Depends(get_current_user_id),
    db=Depends(get_request_db),
):
    policy = await ai_execution_policy_service.get_policy(org_id, db=db)
    return api_success(
        {
            "status": "healthy",
            "policy_mode": policy.mode.value,
            "roles": [
                {
                    "code": "chat",
                    "label": "日常对话与业务任务",
                    "model": policy.primary_model,
                    "status": "active",
                },
                {
                    "code": "embedding",
                    "label": "知识检索",
                    "model": policy.embedding_model,
                    "status": "active",
                },
                {
                    "code": "rerank",
                    "label": "结果精排",
                    "model": policy.rerank_model,
                    "status": "active",
                },
                {
                    "code": "premium",
                    "label": "高价模型备用",
                    "model": policy.premium_model,
                    "status": "manual_only" if policy.premium_model else "disabled",
                },
            ],
            "controls": {
                "automatic_paid_routing": False,
                "scheduled_primary_only": policy.scheduled_primary_only,
                "request_budget_enabled": True,
                "receipt_retention": policy.retain_inference_receipts,
            },
            "trace_id": getattr(request.state, "trace_id", None),
        }
    )
