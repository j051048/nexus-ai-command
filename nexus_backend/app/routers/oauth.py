"""OAuth 2.0 API endpoints."""

import logging
from fastapi import APIRouter, Request, Depends
from app.core.auth import get_current_user_id
from app.core.errors import api_success, api_error, ErrorCode
from app.services.oauth_service import oauth_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/oauth", tags=["OAuth"])


@router.post("/clients")
async def register_client(
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """Register a new OAuth client application."""
    try:
        body = await req.json()
        name = body.get("client_name")
        redirect_uris = body.get("redirect_uris", [])
        scopes = body.get("scopes", ["read"])

        if not name:
            return api_error(ErrorCode.VALIDATION_INVALID_INPUT, "client_name is required")
        if not redirect_uris:
            return api_error(ErrorCode.VALIDATION_INVALID_INPUT, "redirect_uris is required")

        org_id = getattr(req.state, "org_id", None) or "default"
        result = await oauth_service.register_client(
            name=name,
            org_id=org_id,
            redirect_uris=redirect_uris,
            scopes=scopes,
            db=getattr(req.state, "db", None),
        )
        return api_success(data=result)
    except Exception as e:
        logger.error(f"OAuth client registration failed: {e}")
        return api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.get("/authorize")
async def authorize(
    req: Request,
    client_id: str,
    redirect_uri: str,
    scope: str = "read",
    code_challenge: str = None,
    user_id: str = Depends(get_current_user_id),
):
    """Authorization endpoint — generates an authorization code."""
    scopes = scope.split()
    auth_code = await oauth_service.authorize(
        client_id=client_id,
        redirect_uri=redirect_uri,
        scopes=scopes,
        user_id=user_id,
        code_challenge=code_challenge,
    )
    if not auth_code:
        return api_error(ErrorCode.VALIDATION_INVALID_INPUT, "Invalid client or redirect URI")

    return api_success(data={
        "code": auth_code.code,
        "redirect_uri": redirect_uri,
    })


@router.post("/token")
async def exchange_token(req: Request):
    """Token exchange endpoint — exchange code for tokens or refresh."""
    try:
        body = await req.json()
        grant_type = body.get("grant_type")

        if grant_type == "authorization_code":
            token = await oauth_service.exchange_code(
                code=body.get("code", ""),
                client_id=body.get("client_id", ""),
                client_secret=body.get("client_secret", ""),
                redirect_uri=body.get("redirect_uri", ""),
                code_verifier=body.get("code_verifier"),
            )
        elif grant_type == "refresh_token":
            token = await oauth_service.refresh_token(
                refresh_tok=body.get("refresh_token", ""),
                client_id=body.get("client_id", ""),
            )
        else:
            return api_error(ErrorCode.VALIDATION_INVALID_INPUT, "Unsupported grant_type")

        if not token:
            return api_error(ErrorCode.AUTH_TOKEN_EXPIRED, "Invalid or expired credentials")

        return api_success(data=token.to_dict())
    except Exception as e:
        logger.error(f"Token exchange failed: {e}")
        return api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))


@router.post("/revoke")
async def revoke_token(req: Request):
    """Revoke an access or refresh token."""
    try:
        body = await req.json()
        token = body.get("token", "")
        success = await oauth_service.revoke_token(token)
        return api_success(data={"revoked": success})
    except Exception as e:
        return api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, str(e))
