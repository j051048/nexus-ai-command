"""Enterprise SSO endpoints."""

import secrets

from fastapi import APIRouter, Form, HTTPException, Query

from app.core.errors import api_success
from app.services.enterprise_sso_service import EnterpriseSSOError, enterprise_sso_service

router = APIRouter(prefix="/api/enterprise-sso", tags=["Enterprise SSO"])


@router.get("/oidc/login")
async def oidc_login(
    org_id: str = Query(...),
    provider_code: str = Query(...),
    redirect_uri: str = Query(...),
):
    """Return a provider authorization URL with signed state."""
    try:
        result = enterprise_sso_service.build_oidc_login_url(
            org_id=org_id,
            provider_code=provider_code,
            redirect_uri=redirect_uri,
            nonce=secrets.token_urlsafe(18),
        )
        return api_success(data=result)
    except EnterpriseSSOError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/oidc/callback")
async def oidc_callback(
    code: str = Form(...),
    state: str = Form(...),
    redirect_uri: str = Form(...),
):
    """Exchange an OIDC authorization code and return verified identity claims."""
    try:
        result = await enterprise_sso_service.exchange_oidc_code(
            code=code,
            state=state,
            redirect_uri=redirect_uri,
        )
        return api_success(data=result)
    except EnterpriseSSOError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/saml/callback")
async def saml_callback(
    saml_response: str = Form(..., alias="SAMLResponse"),
):
    """Parse a SAML Response. Unsigned assertions are rejected by default."""
    try:
        result = enterprise_sso_service.parse_saml_response(saml_response)
        return api_success(data=result)
    except EnterpriseSSOError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
