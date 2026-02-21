"""
P0 Security: Authentication Module
Critical security fixes applied:
- Fix #2: Remove algorithm confusion attack vector (no dynamic token_alg)
- Fix #3: Remove ALLOW_UNSECURE_AUTH bypass completely
- Fix #8: Remove test: prefix authentication in all environments
- Fix: Support ES256 JWTs via Supabase JWKS endpoint
"""

import jwt
from jwt import PyJWKClient
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

# Supabase URL for JWKS endpoint (ES256 public key auto-discovery)
SUPABASE_URL = os.getenv("SUPABASE_URL", "")

# P0 Security Fix #2: Only allow known, safe algorithms - NO dynamic algorithm from token
# This prevents algorithm confusion attacks (e.g., alg: none)
ALLOWED_ALGORITHMS = ["HS256", "RS256", "ES256"]

# Initialize JWKS client for ES256 verification.
# Supabase publishes its signing public key at /.well-known/jwks.json
# PyJWKClient caches the key automatically (lifespan=300s by default).
_jwks_client: Optional[PyJWKClient] = None
if SUPABASE_URL:
    try:
        jwks_url = f"{SUPABASE_URL.rstrip('/')}/auth/v1/.well-known/jwks.json"
        _jwks_client = PyJWKClient(jwks_url, cache_keys=True, lifespan=600)
        logger.info(f"JWKS client initialized: {jwks_url}")
    except Exception as e:
        logger.warning(f"Failed to initialize JWKS client: {e}")

# P0 Security: Validate critical secrets in production
if IS_PRODUCTION:
    if not SUPABASE_JWT_SECRET and not JWT_SECRET and not _jwks_client:
        raise RuntimeError("CRITICAL: JWT secret or JWKS URL must be configured in production")


async def get_current_user_id(authorization: Optional[str] = Header(None)) -> str:
    """
    P0 Security: Authenticate user via JWT with strict security controls.

    Verification strategy (in order):
    1. JWKS (ES256/RS256) — fetch public key from Supabase JWKS endpoint
    2. HS256 with SUPABASE_JWT_SECRET / JWT_SECRET — traditional shared secret

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

        # Read token header to determine algorithm
        claimed_alg = None
        try:
            unverified_header = jwt.get_unverified_header(token)
            claimed_alg = unverified_header.get("alg")
            if claimed_alg not in ALLOWED_ALGORITHMS:
                logger.warning(f"Token claims unsupported algorithm: {claimed_alg}")
        except Exception:
            pass

        payload = None
        last_error = None

        # Strategy 1: Try JWKS (for ES256/RS256 tokens from Supabase)
        if _jwks_client and claimed_alg in ("ES256", "RS256"):
            try:
                signing_key = _jwks_client.get_signing_key_from_jwt(token)
                payload = jwt.decode(
                    token,
                    signing_key.key,
                    algorithms=["ES256", "RS256"],
                    audience="authenticated",
                    options={
                        "verify_signature": True,
                        "verify_exp": True,
                        "verify_iat": True,
                        "verify_aud": True,
                        "require": ["sub", "exp"],
                    },
                )
                logger.debug(f"JWT verified via JWKS ({claimed_alg})")
            except jwt.ExpiredSignatureError:
                raise HTTPException(
                    status_code=401,
                    detail="登录已过期，请重新登录 (Token expired, please login again)",
                )
            except Exception as e:
                last_error = e
                logger.debug(f"JWKS verification failed: {e}")

        # Strategy 2: Try shared secrets (for HS256 tokens)
        if not payload:
            secrets_to_try = [s for s in [SUPABASE_JWT_SECRET, JWT_SECRET] if s]

            for secret in secrets_to_try:
                try:
                    payload = jwt.decode(
                        token,
                        secret,
                        algorithms=["HS256"],
                        options={
                            "verify_signature": True,
                            "verify_exp": True,
                            "verify_iat": True,
                            "require": ["sub", "exp"],
                        },
                    )
                    logger.debug("JWT verified via shared secret (HS256)")
                    break
                except jwt.InvalidSignatureError as e:
                    last_error = e
                    continue
                except jwt.ExpiredSignatureError:
                    raise HTTPException(
                        status_code=401,
                        detail="登录已过期，请重新登录 (Token expired, please login again)",
                    )
                except jwt.MissingRequiredClaimError as e:
                    logger.warning(f"Token missing required claim: {e}")
                    last_error = e
                    continue
                except Exception as e:
                    last_error = e
                    continue

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
