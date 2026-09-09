"""Lease-guarded, job-local checkpoints. Never cache across actors or jobs."""

import hashlib
import json
from types import SimpleNamespace
from typing import Any

CHECKPOINT_VERSION = "delivery-stages.v1"


def _json_default(value):
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    raise TypeError(f"Unsupported checkpoint input: {type(value).__name__}")


class ArtifactStageCache:
    def __init__(
        self,
        *,
        db=None,
        organization_id=None,
        user_id=None,
        job_id=None,
        lease_token=None,
        context=None,
    ):
        if bool(job_id) != bool(lease_token):
            raise ValueError("Job and lease are required together")
        self.db = db
        self.scope = dict(
            p_organization_id=organization_id,
            p_user_id=user_id,
            p_job_id=job_id,
            p_lease_token=lease_token,
        )
        self.context = context or {}
        self.hits = 0

    async def pair(self, stage, operation, **kwargs):
        if not self.scope["p_job_id"]:
            return await operation(**kwargs)
        fingerprint = hashlib.sha256(
            json.dumps(
                [CHECKPOINT_VERSION, self.context, kwargs],
                ensure_ascii=False,
                sort_keys=True,
                default=_json_default,
            ).encode()
        ).hexdigest()
        args = {**self.scope, "p_stage": stage, "p_input_hash": fingerprint}
        cached = await self.db.rpc("artifact_stage_checkpoint", args).execute()
        payload = cached.data
        if isinstance(payload, dict) and payload.get("schema") == CHECKPOINT_VERSION:
            self.hits += 1
            return payload["value"], SimpleNamespace(**payload["response"])
        value, response = await operation(**kwargs)
        # Partial, errored and fallback-only generations must not become checkpoints.
        if (
            response is None
            or getattr(response, "finish_reason", None) in {"error", "length"}
            or not value
        ):
            return value, response
        safe_response = {
            "model_code": getattr(response, "model_code", ""),
            "usage": getattr(response, "usage", None) or {},
            "finish_reason": getattr(response, "finish_reason", "stop"),
        }
        checkpoint = {
            "schema": CHECKPOINT_VERSION,
            "value": value,
            "response": safe_response,
        }
        await self.db.rpc(
            "artifact_stage_checkpoint",
            {
                **args,
                "p_payload": checkpoint,
            },
        ).execute()
        return value, response


def merge_delivery_usage(*usages: dict[str, Any] | None) -> dict[str, int | float]:
    """Keep provider-reported cost decimals; unknown cost is absent, not zero."""
    totals: dict[str, int | float] = {}
    for usage in usages:
        for key in ("input_tokens", "output_tokens", "total_tokens", "call_cost"):
            value = (usage or {}).get(key)
            if isinstance(value, int | float) and not isinstance(value, bool):
                totals[key] = totals.get(key, 0) + value
    return totals
