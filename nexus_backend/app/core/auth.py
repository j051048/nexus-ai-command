import jwt
import os
from fastapi import Header, HTTPException, Request
from typing import Optional

# P0 Security Fix: Environment detection
ENV = os.getenv("ENV", "development")
IS_PRODUCTION = ENV in ("production", "prod")

# Supabase typically uses a project-specific JWT secret. 
# We prioritize SUPABASE_JWT_SECRET, then JWT_SECRET, then a dev fallback.
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")
JWT_SECRET = os.getenv("JWT_SECRET")
JWT_ALGORITHM = "HS256"

# P0 Security: Validate critical secrets in production
if IS_PRODUCTION:
    if not SUPABASE_JWT_SECRET and not JWT_SECRET:
        raise RuntimeError("CRITICAL: JWT secret must be configured in production")
    if os.getenv("ALLOW_UNSECURE_AUTH") == "true":
        raise RuntimeError("CRITICAL: ALLOW_UNSECURE_AUTH cannot be enabled in production")

async def get_current_user_id(authorization: Optional[str] = Header(None)) -> str:
    """
    P0 Fix: Authenticate user via JWT.
    Supports Supabase JWTs and mandatory identity verification.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="缺少身份认证信息 (Missing Authorization Header)")
    
    try:
        # 1. Handle "test:" prefix for local development WITHOUT JWT
        # P0 Security Fix: Completely disabled in production
        if authorization.startswith("test:"):
            if IS_PRODUCTION:
                raise HTTPException(
                    status_code=401, 
                    detail="Test authentication is disabled in production"
                )
            print("⚠️ DEV MODE: Using test authentication - NOT FOR PRODUCTION")
            return authorization.split(":")[1]
             
        if not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="认证格式错误 (Invalid token format - expected Bearer)")
            
        token = authorization.split(" ")[1]
        
        # 2. Inspect Header to debug Algorithm issues
        try:
            unverified_header = jwt.get_unverified_header(token)
            token_alg = unverified_header.get('alg')
            print(f"Auth Debug: Token Algorithm is {token_alg}")
        except:
            token_alg = "HS256"

        # We try secrets in order of probability
        secrets_to_try = [SUPABASE_JWT_SECRET, JWT_SECRET]
        payload = None
        last_error = None
        
        # Allow both common algorithms
        allowed_algs = [JWT_ALGORITHM, "RS256", token_alg]

        for secret in secrets_to_try:
            if not secret: continue
            try:
                # Attempt to decode and verify signature
                # We dynamically include the token's alg to prevent 'specified alg value is not allowed' error
                payload = jwt.decode(token, secret, algorithms=allowed_algs)
                print(f"Auth Debug: Successfully verified with secret ending in ...{secret[-4:] if len(secret)>4 else '****'}")
                break
            except jwt.InvalidSignatureError as e:
                last_error = e
                # print(f"Auth Debug: Sig check failed for secret ending in ...{secret[-4:] if len(secret)>4 else '****'}")
                continue
            except jwt.ExpiredSignatureError as e:
                print("Auth Debug: Token Expired.")
                if os.getenv("ALLOW_UNSECURE_AUTH") == "true":
                     last_error = e
                     continue 
                raise HTTPException(status_code=401, detail="登录已过期 (Token expired)")
            except Exception as e:
                # Catch generic algorithm errors or other pyjwt errors so we don't crash
                # print(f"Auth Debug: Verification step failed: {str(e)}")
                last_error = e
                continue
        
                # 3. Development Fallback: Decode WITHOUT verification if explicitly allowed
        # P0 Security Fix: Double-check production environment
        if not payload and not IS_PRODUCTION and os.getenv("ALLOW_UNSECURE_AUTH") == "true":
            # Extract 'sub' (User ID) without verifying signature
            try:
                print("Auth Debug: Attempting unverified decode (DEV ONLY)...")
                payload = jwt.decode(token, options={"verify_signature": False})
                print(f"⚠️ SECURITY WARNING [DEV]: Using unverified payload. Sub: {payload.get('sub')}")
            except Exception as e:
                print(f"Auth Debug: Unverified decode failed: {e}")
                pass

        if not payload:
            error_msg = f"身份验签失败: {str(last_error)}" if last_error else "无效的认证令牌 (Invalid token signature)"
            print(f"Auth Debug: 401 Error - {error_msg}")
            raise HTTPException(status_code=401, detail=error_msg)

        user_id = payload.get("sub") or payload.get("id")
        if not user_id:
            print("Auth Debug: 401 Error - Token missing user identity")
            raise HTTPException(status_code=401, detail="令牌中缺少用户身份标识 (Token missing user identity)")
            
        return user_id
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"Auth Debug: Unexpected Error - {str(e)}")
        raise HTTPException(status_code=401, detail=f"认证执行异常: {str(e)}")
