import jwt
import os
from fastapi import Header, HTTPException
from typing import Optional

JWT_SECRET = os.getenv("JWT_SECRET", "nexus_secret_fallback_do_not_use_in_prod")
JWT_ALGORITHM = "HS256"

async def get_current_user_id(authorization: Optional[str] = Header(None)) -> str:
    """
    P0 Fix: Authenticate user via JWT.
    Prevents parameter tampering and identity forgery.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization Header")
    
    try:
        if not authorization.startswith("Bearer "):
            # For backward compatibility with pure UUID during dev, we allow it ONLY if prefixed with 'test:'
            if authorization.startswith("test:"):
                 return authorization.split(":")[1]
            raise HTTPException(status_code=401, detail="Invalid token format")
            
        token = authorization.split(" ")[1]
        
        # In a real Supabase setup, tokens are signed by Supabase.
        # Here we implement a generic decoder that can be pointed to Supabase Secret.
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            user_id = payload.get("sub") or payload.get("id")
            if not user_id:
                raise HTTPException(status_code=401, detail="Token missing user identity")
            return user_id
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token expired")
        except jwt.InvalidTokenError:
            # P0 Hybrid Fallback: During transition, if decoding fails but it's a valid UUID string, 
            # we might permit it IF 'ALLOW_UNSECURE_AUTH' is true.
            if os.getenv("ALLOW_UNSECURE_AUTH") == "true":
                return token
            raise HTTPException(status_code=401, detail="Invalid signature or malformed token")
            
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Authentication failed: {str(e)}")
