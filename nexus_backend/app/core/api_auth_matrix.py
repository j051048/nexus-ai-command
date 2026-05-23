"""Explicit allowlist for intentionally public API routes.

Most `/api` endpoints must be protected by FastAPI auth dependencies. The
entries below are the narrow exceptions: public metadata, browser bootstrap
values, OAuth/SSO exchanges, and third-party callbacks that authenticate through
their own protocol signatures or state tokens.
"""

from __future__ import annotations

from typing import Final

RouteKey = tuple[str, str]


PUBLIC_API_ROUTE_REASONS: Final[dict[RouteKey, str]] = {
    ("GET", "/api/ping"): "read-only service reachability probe",
    ("GET", "/api/chat/prompts/manifest"): "prompt hashes and metadata only",
    ("GET", "/api/tools/capabilities"): "read-only tool capability catalog",
    ("POST", "/api/metrics/web-vitals"): "anonymous browser telemetry ingest",
    ("GET", "/api/crm/stages"): "static CRM stage metadata",
    ("GET", "/api/crm/activity-types"): "static CRM activity type metadata",
    ("GET", "/api/workflows/types"): "static workflow type metadata",
    ("GET", "/api/billing/plans"): "public pricing plan catalog",
    ("POST", "/api/billing/webhook"): "payment provider callback",
    ("POST", "/api/payments/callback/{platform}"): "payment provider callback",
    ("POST", "/api/webhooks/stripe"): "Stripe signature-authenticated callback",
    ("POST", "/api/im-chat/feishu/event"): "Feishu callback protocol endpoint",
    ("POST", "/api/im-chat/wecom/event"): "WeCom callback protocol endpoint",
    ("GET", "/api/im-auth/{platform}/login-url"): "OAuth login bootstrap",
    ("GET", "/api/im-auth/{platform}/callback"): "OAuth provider callback",
    ("POST", "/api/im-callback/{platform}/approval"): "IM signed card callback",
    ("POST", "/api/oauth/token"): "OAuth token exchange endpoint",
    ("POST", "/api/oauth/revoke"): "OAuth token revocation endpoint",
    ("GET", "/api/enterprise-sso/oidc/login"): "OIDC login bootstrap",
    ("POST", "/api/enterprise-sso/oidc/callback"): "OIDC provider callback",
    ("POST", "/api/enterprise-sso/saml/callback"): "SAML provider callback",
    ("GET", "/api/push/vapid-key"): "public Web Push VAPID key",
    ("GET", "/api/wecom/callback"): "WeCom URL verification callback",
    ("POST", "/api/wecom/callback"): "WeCom message callback",
    ("GET", "/api/docs/openapi-enhanced"): "public API documentation",
    ("GET", "/api/docs/stats"): "public API documentation metadata",
    ("GET", "/api/docs/examples"): "public API documentation examples",
    ("GET", "/api/docs/changelog"): "public API documentation changelog",
    ("GET", "/api/docs/tags"): "public API documentation tags",
    ("GET", "/api/llm/available-models"): "public LLM marketplace catalog",
}


def is_intentionally_public_api_route(method: str, path: str) -> bool:
    return (method.upper(), path) in PUBLIC_API_ROUTE_REASONS
