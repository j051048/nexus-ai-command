"""
P0 Security: Authentication Module
Critical security fixes applied:
- Fix #2: Remove algorithm confusion attack vector (no dynamic token_alg)
- Fix #3: Remove ALLOW_UNSECURE_AUTH bypass completely
- Fix #8: Remove test: prefix authentication in all environments
"""

import jwt
import os
import logging
from fastapi import Header, HTTPException
from typing import Optional

# Use structured logging instead of print
logger = logging.getLogger(__name__)

# P0 Security Fix: Environment detection
ENV = os.getenv("ENV", "development")
IS_PRODUCTION = ENV in ("production", "prod")
IS_TEST = ENV == "test"

# Supabase typically uses a project-specific JWT secret.
# We prioritize SUPABASE_JWT_SECRET, then JWT_SECRET.
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")
JWT_SECRET = os.getenv("JWT_SECRET")

# P0 Security Fix #2: Only allow known, safe algorithms - NO dynamic algorithm from token
# This prevents algorithm confusion attacks (e.g., alg: none)
ALLOWED_ALGORITHMS = ["HS256", "RS256", "ES256"]

# P0 Security: Validate critical secrets in production
if IS_PRODUCTION:
    if not SUPABASE_JWT_SECRET and not JWT_SECRET:
        raise RuntimeError("CRITICAL: JWT secret must be configured in production")


async def get_current_user_id(authorization: Optional[str] = Header(None)) -> str:
    """
    P0 Security: Authenticate user via JWT with strict security controls.

    Security measures:
    - Fixed algorithm whitelist (no dynamic algorithms from token)
    - No signature bypass in any environment
    - Removed test: prefix authentication
    """
    if not authorization:
        raise HTTPException(
            status_code=401, detail="缺少身份认证信息 (Missing Authorization Header)"
        )

    try:
        # P0 Security Fix #8: Remove test: prefix authentication entirely
        # This was a security hole that allowed arbitrary user impersonation
        if authorization.startswith("test:"):
            logger.warning("Blocked attempt to use deprecated test: authentication")
            raise HTTPException(
                status_code=401,
                detail="test: 认证方式已被禁用 (test: authentication has been disabled for security)",
            )

        if not authorization.startswith("Bearer "):
            raise HTTPException(
                status_code=401,
                detail="认证格式错误 (Invalid token format - expected Bearer)",
            )

        token = authorization.split(" ")[1]

        # P0 Security Fix #2: Do NOT read algorithm from token header
        # This prevents algorithm confusion attacks where attacker sets alg: none
        # We only log what the token claims, but DO NOT use it for verification
        try:
            unverified_header = jwt.get_unverified_header(token)
            claimed_alg = unverified_header.get("alg")
            if claimed_alg not in ALLOWED_ALGORITHMS:
                logger.warning(f"Token claims unsupported algorithm: {claimed_alg}")
                # We still proceed with our fixed algorithm list
        except Exception:
            pass  # Don't fail on header parsing, just proceed with verification

        # Try secrets in order of probability
        secrets_to_try = [s for s in [SUPABASE_JWT_SECRET, JWT_SECRET] if s]

        if not secrets_to_try:
            logger.error("No JWT secrets configured")
            raise HTTPException(
                status_code=500, detail="服务器配置错误 (Server configuration error)"
            )

        payload = None
        last_error = None

        for secret in secrets_to_try:
            try:
                # P0 Security Fix #2: Use FIXED algorithm list, never dynamic
                payload = jwt.decode(
                    token,
                    secret,
                    algorithms=ALLOWED_ALGORITHMS,
                    options={
                        "verify_signature": True,  # Always verify
                        "verify_exp": True,  # Check expiration
                        "verify_iat": True,  # Check issued at
                        "require": ["sub", "exp"],  # Require these claims
                    },
                )
                logger.debug("JWT verified successfully")
                break
            except jwt.InvalidSignatureError as e:
                last_error = e
                continue
            except jwt.ExpiredSignatureError:
                # P0 Security Fix #3: No bypass for expired tokens
                raise HTTPException(
                    status_code=401,
                    detail="登录已过期，请重新登录 (Token expired, please login again)",
                )
            except jwt.InvalidAlgorithmError as e:
                # This catches attempts to use unsupported algorithms
                logger.warning(f"Invalid algorithm attempted: {e}")
                last_error = e
                continue
            except jwt.MissingRequiredClaimError as e:
                logger.warning(f"Token missing required claim: {e}")
                last_error = e
                continue
            except Exception as e:
                last_error = e
                continue

        # P0 Security Fix #3: REMOVED - No unverified decode fallback
        # The old code had: if not payload and ALLOW_UNSECURE_AUTH: jwt.decode(..., verify_signature=False)
        # This has been completely removed to prevent signature bypass attacks

        if not payload:
            error_msg = "身份验签失败 (Authentication failed)"
            if last_error:
                logger.warning(
                    f"Auth failure reason: {type(last_error).__name__}: {last_error}"
                )
            raise HTTPException(status_code=401, detail=error_msg)

        user_id = payload.get("sub") or payload.get("id")
        if not user_id:
            raise HTTPException(
                status_code=401,
                detail="令牌中缺少用户身份标识 (Token missing user identity)",
            )

        return user_id

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Unexpected auth error: {e}")
        raise HTTPException(
            status_code=401, detail="认证执行异常 (Authentication error)"
        )
