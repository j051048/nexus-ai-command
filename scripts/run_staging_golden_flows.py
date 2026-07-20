#!/usr/bin/env python3
"""Run the smallest real production proof against an isolated staging tenant.

The runner intentionally uses public HTTP contracts rather than importing app
internals. It creates uniquely tagged data, exercises the streaming Agent,
approval and solution-delivery workflows, proves cross-tenant denial, and
archives or removes its fixtures.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

import httpx

REQUIRED_ENV = (
    "STAGING_API_URL",
    "STAGING_GOLDEN_ORG_ID",
    "STAGING_EMPLOYEE_TOKEN",
    "STAGING_BOSS_TOKEN",
    "STAGING_OTHER_ORG_CUSTOMER_ID",
)


class GoldenFlowError(RuntimeError):
    """Raised when a real staging contract does not hold."""


def _data(payload: dict[str, Any]) -> Any:
    return payload.get("data", payload)


def _assert_status(response: httpx.Response, expected: set[int], step: str) -> None:
    if response.status_code not in expected:
        body = response.text[:800]
        raise GoldenFlowError(
            f"{step}: expected HTTP {sorted(expected)}, got "
            f"{response.status_code}: {body}"
        )


def parse_sse_payloads(body: str) -> tuple[list[dict[str, Any]], bool]:
    """Parse data-only SSE used by the Agent endpoint."""
    payloads: list[dict[str, Any]] = []
    completed = False
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if not line.startswith("data:"):
            continue
        value = line.removeprefix("data:").strip()
        if value == "[DONE]":
            completed = True
            continue
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            raise GoldenFlowError(f"agent: invalid SSE JSON: {value[:200]}") from exc
        if isinstance(parsed, dict):
            payloads.append(parsed)
    return payloads, completed


@dataclass(frozen=True)
class StagingGoldenConfig:
    api_url: str
    org_id: str
    employee_token: str
    boss_token: str
    other_org_customer_id: str

    @classmethod
    def from_env(cls) -> StagingGoldenConfig:
        missing = [name for name in REQUIRED_ENV if not os.getenv(name)]
        if missing:
            raise GoldenFlowError(
                "Missing staging golden-flow environment variables: "
                + ", ".join(missing)
            )
        return cls(
            api_url=os.environ["STAGING_API_URL"].rstrip("/"),
            org_id=os.environ["STAGING_GOLDEN_ORG_ID"],
            employee_token=os.environ["STAGING_EMPLOYEE_TOKEN"],
            boss_token=os.environ["STAGING_BOSS_TOKEN"],
            other_org_customer_id=os.environ["STAGING_OTHER_ORG_CUSTOMER_ID"],
        )


class StagingGoldenFlowRunner:
    def __init__(self, config: StagingGoldenConfig, client: httpx.AsyncClient):
        self.config = config
        self.client = client
        self.run_id = str(uuid4())
        self.customer_id: str | None = None
        self.solution_project_id: str | None = None

    def _headers(self, token: str, operation: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "X-Idempotency-Key": f"staging-golden-{operation}-{self.run_id}",
        }

    async def create_customer(self) -> None:
        response = await self.client.post(
            "/api/crm/customers",
            headers=self._headers(self.config.employee_token, "customer"),
            json={
                "name": f"QA 光谱客户 {self.run_id[:8]}",
                "company": "Nexus Staging Golden Flow",
                "industry": "科学仪器",
                "stage": "lead",
                "source": "staging_golden_flow",
                "instrument_line_code": "spectroscopy",
                "application_fields": ["材料分析"],
                "metadata": {"golden_flow_run_id": self.run_id},
            },
        )
        _assert_status(response, {200, 201}, "crm.create_customer")
        customer = _data(response.json()).get("customer", {})
        self.customer_id = str(customer.get("id") or "")
        if not self.customer_id:
            raise GoldenFlowError("crm.create_customer: missing customer id")
        if str(customer.get("organization_id")) != self.config.org_id:
            raise GoldenFlowError("crm.create_customer: tenant context mismatch")

    async def invoke_agent(self) -> None:
        response = await self.client.post(
            "/api/chat",
            headers=self._headers(self.config.employee_token, "agent"),
            json={
                "messages": [
                    {
                        "role": "user",
                        "content": (
                            f"为客户 {self.customer_id} 生成一条简短的光谱仪销售跟进建议，"
                            "并说明下一步动作。"
                        ),
                    }
                ],
                "agent": "crm",
                "sessionId": f"staging-golden-{self.run_id}",
            },
            timeout=90,
        )
        _assert_status(response, {200}, "agent.chat")
        if "text/event-stream" not in response.headers.get("content-type", ""):
            raise GoldenFlowError("agent.chat: response is not SSE")
        payloads, completed = parse_sse_payloads(response.text)
        if not completed:
            raise GoldenFlowError("agent.chat: stream did not emit [DONE]")
        content = "".join(
            str(item.get("choices", [{}])[0].get("delta", {}).get("content", ""))
            for item in payloads
            if item.get("choices")
        )
        if not content.strip():
            raise GoldenFlowError("agent.chat: no user-visible content")
        if any(item.get("error") for item in payloads):
            raise GoldenFlowError("agent.chat: stream emitted an error event")

    async def submit_approval(self) -> None:
        response = await self.client.post(
            "/api/approval/submit-smart",
            headers=self._headers(self.config.employee_token, "approval-submit"),
            json={
                "type": "purchase",
                "amount": 1,
                "description": f"Staging golden flow {self.run_id}",
                "form_data": {"golden_flow_run_id": self.run_id},
            },
        )
        _assert_status(response, {200, 201}, "approval.submit")
        result = _data(response.json())
        request_id = str(result.get("request_id") or "")
        if not request_id:
            raise GoldenFlowError("approval.submit: missing request id")
        if result.get("auto_approved"):
            return

        advance = await self.client.post(
            f"/api/approval/{request_id}/advance",
            headers=self._headers(self.config.boss_token, "approval-advance"),
            json={"decision": "approved", "comment": "staging golden flow"},
        )
        _assert_status(advance, {200}, "approval.advance")
        updated = _data(advance.json()).get("updated_request", {})
        if updated.get("status") not in {"pending", "approved"}:
            raise GoldenFlowError("approval.advance: invalid resulting status")

    async def prove_solution_workflow(self) -> None:
        if not self.customer_id:
            raise GoldenFlowError("solution.create: customer fixture is missing")
        create = await self.client.post(
            "/api/solution-workspace/projects",
            headers=self._headers(self.config.employee_token, "solution-create"),
            json={
                "title": f"Staging spectroscopy solution {self.run_id[:8]}",
                "customer_id": self.customer_id,
                "customer_name": "Nexus Staging Golden Flow",
                "industry": "高校科研",
                "region": "staging",
                "budget_min": 100000,
                "budget_max": 500000,
                "instrument_line_code": "spectroscopy",
                "application_scenario": "Material characterization and method validation",
                "scenario_pack_code": "spectroscopy:高校科研",
            },
        )
        _assert_status(create, {200, 201}, "solution.create")
        project = _data(create.json())
        self.solution_project_id = str(project.get("id") or "")
        if not self.solution_project_id:
            raise GoldenFlowError("solution.create: missing project id")

        generated = await self.client.post(
            f"/api/solution-workspace/projects/{self.solution_project_id}/generate",
            headers=self._headers(self.config.employee_token, "solution-generate"),
            timeout=120,
        )
        _assert_status(generated, {200}, "solution.generate")
        generated_data = _data(generated.json())
        generated_project = generated_data.get("project") or {}
        workspace = generated_project.get("workspace") or {}
        if not workspace.get("sections") or not workspace.get("packages"):
            raise GoldenFlowError("solution.generate: missing generated workspace")

        evidence_ref = f"staging-golden:{self.run_id}"
        workspace["active_stage"] = "delivery"
        workspace["requirements"] = [
            {
                **item,
                "status": "verified",
                "evidence_ref": item.get("evidence_ref") or evidence_ref,
            }
            for item in workspace.get("requirements") or []
        ]
        workspace["sections"] = [
            {
                **item,
                "status": "approved",
                "evidence_refs": item.get("evidence_refs") or [evidence_ref],
            }
            for item in workspace.get("sections") or []
        ]
        workspace["review_gates"] = [
            {**item, "passed": True} for item in workspace.get("review_gates") or []
        ]
        # The golden flow validates orchestration, not a tenant's private price
        # catalog. Removing model guesses prevents fabricated SKUs from passing
        # the deterministic commercial gate.
        workspace["packages"] = [
            {**item, "product_models": [], "line_items": []}
            for item in workspace.get("packages") or []
        ]
        saved = await self.client.put(
            f"/api/solution-workspace/projects/{self.solution_project_id}/workspace",
            headers=self._headers(self.config.employee_token, "solution-save"),
            json=workspace,
        )
        _assert_status(saved, {200}, "solution.save")

        evaluated = await self.client.post(
            f"/api/solution-workspace/projects/{self.solution_project_id}/evaluate",
            headers=self._headers(self.config.employee_token, "solution-evaluate"),
        )
        _assert_status(evaluated, {200}, "solution.evaluate")
        if not _data(evaluated.json()).get("ready"):
            raise GoldenFlowError("solution.evaluate: quality gate did not pass")

        readiness = await self.client.get(
            f"/api/solution-workspace/projects/{self.solution_project_id}/tender-readiness",
            headers=self._headers(
                self.config.employee_token, "solution-tender-readiness"
            ),
        )
        _assert_status(readiness, {200}, "solution.tender_readiness")
        if _data(readiness.json()).get("decision") != "bid":
            raise GoldenFlowError("solution.tender_readiness: expected bid decision")

        exported = await self.client.get(
            f"/api/solution-workspace/projects/{self.solution_project_id}/export",
            params={"format": "markdown"},
            headers=self._headers(self.config.employee_token, "solution-export"),
        )
        _assert_status(exported, {200}, "solution.export")
        if len(exported.content) < 100:
            raise GoldenFlowError(
                "solution.export: generated artifact is unexpectedly empty"
            )

    async def prove_tenant_isolation(self) -> None:
        response = await self.client.get(
            f"/api/crm/customers/{self.config.other_org_customer_id}",
            headers=self._headers(self.config.employee_token, "cross-tenant-read"),
        )
        _assert_status(response, {403, 404}, "tenant.cross_org_read")

    async def cleanup(self) -> None:
        if self.solution_project_id:
            response = await self.client.patch(
                f"/api/solution-workspace/projects/{self.solution_project_id}",
                headers=self._headers(self.config.boss_token, "cleanup-solution"),
                json={"status": "archived"},
            )
            _assert_status(response, {200}, "solution.cleanup_project")
        if not self.customer_id:
            return
        response = await self.client.delete(
            f"/api/crm/customers/{self.customer_id}",
            headers=self._headers(self.config.boss_token, "cleanup-customer"),
        )
        _assert_status(response, {200, 204}, "crm.cleanup_customer")

    async def run(self) -> None:
        try:
            await self.create_customer()
            await self.invoke_agent()
            await self.submit_approval()
            await self.prove_solution_workflow()
            await self.prove_tenant_isolation()
        finally:
            await self.cleanup()


async def _main() -> int:
    config = StagingGoldenConfig.from_env()
    async with httpx.AsyncClient(
        base_url=config.api_url, follow_redirects=False
    ) as client:
        runner = StagingGoldenFlowRunner(config, client)
        await runner.run()
        print(f"STAGING_GOLDEN_FLOWS_OK run_id={runner.run_id}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(_main()))
    except GoldenFlowError as exc:
        print(f"STAGING_GOLDEN_FLOWS_FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
