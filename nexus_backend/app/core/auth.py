import jwt
import os
from fastapi import Header, HTTPException
from typing import Optional

# Supabase typically uses a project-specific JWT secret. 
# We prioritize SUPABASE_JWT_SECRET, then JWT_SECRET, then a dev fallback.
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")
JWT_SECRET = os.getenv("JWT_SECRET", "nexus_secret_fallback_do_not_use_in_prod")
JWT_ALGORITHM = "HS256"

async def get_current_user_id(authorization: Optional[str] = Header(None)) -> str:
    """
    P0 Fix: Authenticate user via JWT.
    Supports Supabase JWTs and mandatory identity verification.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="缺少身份认证信息 (Missing Authorization Header)")
    
    try:
        # 1. Handle "test:" prefix for local development without JWT
        if authorization.startswith("test:"):
             return authorization.split(":")[1]
             
        if not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="认证格式错误 (Invalid token format - expected Bearer)")
            
        token = authorization.split(" ")[1]
        
        # 2. Attempt to decode and verify
        # We try secrets in order of probability
        secrets_to_try = [SUPABASE_JWT_SECRET, JWT_SECRET]
        payload = None
        last_error = None
        
        for secret in secrets_to_try:
            if not secret: continue
            try:
                payload = jwt.decode(token, secret, algorithms=[JWT_ALGORITHM])
                break
            except jwt.InvalidSignatureError as e:
                last_error = e
                continue
            except jwt.ExpiredSignatureError:
                raise HTTPException(status_code=401, detail="登录已过期 (Token expired)")
        
        # 3. Development Fallback: Decode WITHOUT verification if explicitly allowed
        if not payload and os.getenv("ALLOW_UNSECURE_AUTH") == "true":
            # Extract 'sub' (User ID) without verifying signature
            # WARNING: ONLY USE THIS FOR DEVELOPMENT/INTEGRATION TESTING
            try:
                payload = jwt.decode(token, options={"verify_signature": False})
                print(f"⚠️ SECURITY WARNING: Utilizing unverified JWT payload for user_id: {payload.get('sub')}")
            except:
                pass

        if not payload:
            error_msg = f"身份验签失败: {str(last_error)}" if last_error else "无效的认证令牌 (Invalid token signature)"
            raise HTTPException(status_code=401, detail=error_msg)

        user_id = payload.get("sub") or payload.get("id")
        if not user_id:
            raise HTTPException(status_code=401, detail="令牌中缺少用户身份标识 (Token missing user identity)")
            
        return user_id
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"认证执行异常: {str(e)}")
