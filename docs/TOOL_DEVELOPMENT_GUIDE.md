# Tool Development Guide

This guide keeps new AI tools production-safe, searchable, and cheap enough to run in the agent loop.

## Registration Contract

Register every new tool with `@register_tool` from `nexus_backend/app/tools/registry.py`.

```python
from app.tools.base_tool import BaseTool
from app.tools.registry import register_tool

@register_tool(
    name="crm_update_customer_stage",
    category="crm",
    description="Update a customer's sales stage after validating ownership.",
    required_role="sales",
    risk="medium",
    owner="crm",
    timeout_s=10,
    idempotent=True,
    side_effect=True,
)
class CRMUpdateCustomerStageTool(BaseTool):
    ...
```

Required metadata:

- `name`: stable snake_case identifier; never reuse for a different behavior.
- `category`: one business domain, such as `crm`, `finance`, `hr`, `oa`, `vmd`, `documents`.
- `description`: one sentence describing the business action and the primary entity.
- `required_role`: minimum role needed to call the tool.
- `risk`: `low`, `medium`, `high`, or `critical`.
- `owner`: domain owner responsible for incidents and tests.
- `timeout_s`: hard timeout expectation.
- `idempotent`: `true` only when safe to retry with the same input.
- `side_effect`: `true` for writes, external calls, notifications, payments, approvals, or sync jobs.

## Safety Rules

- Destructive or irreversible tools must set `is_irreversible=True`, `risk="high"` or `risk="critical"`, `idempotent=False`, and `side_effect=True`.
- Tools must derive `org_id` from trusted auth/session context. Do not accept tenant identity from user text.
- Write tools must return enough identifiers for audit and replay, such as record id, status, and operation id.
- External integration tools must set short timeouts and return structured failures instead of raw provider errors.
- Tools should avoid LLM calls inside loops. Batch data first, then call the model once if analysis is needed.

## Error Handling

Use structured errors that can be mapped by `nexus_backend/app/agent/error_message_mapper.py`.

Preferred patterns:

- `PERMISSION_DENIED: ...`
- `VALIDATION_ERROR: ...`
- `NOT_FOUND: ...`
- `CONFLICT: ...`
- `EXTERNAL_TIMEOUT: ...`
- `EXTERNAL_UNAVAILABLE: ...`

Avoid leaking stack traces, SQL, provider secrets, or raw access tokens in returned strings.

## Tool RAG Readiness

Semantic Tool RAG works best when descriptions are short and specific. Include:

- Main verb: create, update, approve, search, summarize, sync.
- Main entity: customer, contract, approval request, invoice, VMD clue.
- Domain noun: CRM, finance, HR, OA, VMD.

Poor description:

`Handle data.`

Good description:

`Search CRM customers by name, owner, status, and recent activity.`

## Test Minimum

For each new tool, add at least:

- A unit test for valid input.
- A unit test for missing required fields.
- A permission or tenant isolation test for write/high-risk tools.
- A timeout or external failure test for integration tools.

## Release Checklist

- Metadata appears in `get_all_tool_manifests()`.
- Tool is covered by RBAC or explicit domain policy.
- High-risk tools trigger HITL or irreversible-tool confirmation.
- No customer-visible mock wording is returned in production paths.
- Errors map to a friendly message.
