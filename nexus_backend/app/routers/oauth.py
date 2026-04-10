"""OAuth 2.0 API endpoints."""

import logging

from fastapi import APIRouter, Depends, Request

from app.core.auth import get_current_user_id
from app.core.errors import ErrorCode, api_error, api_success
from app.models.schemas import OAuthClientCreate, OAuthRevokeRequest, OAuthTokenRequest
from app.services.oauth_service import oauth_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/oauth", tags=["OAuth"])


@router.post("/clients")
async def register_client(
    body: OAuthClientCreate,
    req: Request,
    user_id: str = Depends(get_current_user_id),
):
    """Register a new OAuth client application."""
    try:
        org_id = getattr(req.state, "org_id", None)
        if not org_id:
            raise api_error(ErrorCode.FORBIDDEN, "未关联组织")
        result = await oauth_service.register_client(
            name=body.client_name,
            org_id=org_id,
            redirect_uris=body.redirect_uris,
            scopes=body.scopes,
            db=getattr(req.state, "db", None),
        )
        return api_success(data=result)
    except Exception as e:
        logger.error(f"OAuth client registration failed: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "OAuth授权操作失败")


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
        raise api_error(
            ErrorCode.VALIDATION_INVALID_INPUT, "Invalid client or redirect URI"
        )

    return api_success(
        data={
            "code": auth_code.code,
            "redirect_uri": redirect_uri,
        }
    )


@router.post("/token")
async def exchange_token(body: OAuthTokenRequest):
    """Token exchange endpoint — exchange code for tokens or refresh."""
    try:
        if body.grant_type == "authorization_code":
            token = await oauth_service.exchange_code(
                code=body.code or "",
                client_id=body.client_id or "",
                client_secret=body.client_secret or "",
                redirect_uri=body.redirect_uri or "",
                code_verifier=body.code_verifier,
            )
        elif body.grant_type == "refresh_token":
            token = await oauth_service.refresh_token(
                refresh_tok=body.refresh_token or "",
                client_id=body.client_id or "",
            )
        else:
            raise api_error(
                ErrorCode.VALIDATION_INVALID_INPUT, "Unsupported grant_type"
            )

        if not token:
            raise api_error(
                ErrorCode.AUTH_TOKEN_EXPIRED, "Invalid or expired credentials"
            )

        return api_success(data=token.to_dict())
    except Exception as e:
        logger.error(f"Token exchange failed: {e}")
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "OAuth授权操作失败")


@router.post("/revoke")
async def revoke_token(body: OAuthRevokeRequest):
    """Revoke an access or refresh token."""
    try:
        success = await oauth_service.revoke_token(body.token)
        return api_success(data={"revoked": success})
    except Exception:
        raise api_error(ErrorCode.SYSTEM_INTERNAL_ERROR, "OAuth授权操作失败")
