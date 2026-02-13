"""
OAuth 2.0 provider with authorization code flow and PKCE support.

Implements client registration, authorization code grant, token exchange,
refresh tokens, and token revocation.
"""

import hashlib
import hmac
import logging
import secrets
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class GrantType(Enum):
    """Supported OAuth 2.0 grant types."""
    AUTHORIZATION_CODE = "authorization_code"
    CLIENT_CREDENTIALS = "client_credentials"
    REFRESH_TOKEN = "refresh_token"


@dataclass
class OAuthClient:
    """A registered OAuth client application."""
    client_id: str
    client_secret_hash: str
    client_name: str
    org_id: str
    redirect_uris: List[str]
    allowed_scopes: List[str]
    grant_types: List[str] = field(default_factory=lambda: ["authorization_code"])
    is_active: bool = True
    created_at: str = ""

    def to_dict(self) -> Dict:
        return {
            "client_id": self.client_id,
            "client_name": self.client_name,
            "org_id": self.org_id,
            "redirect_uris": self.redirect_uris,
            "allowed_scopes": self.allowed_scopes,
            "grant_types": self.grant_types,
            "is_active": self.is_active,
        }


@dataclass
class AuthorizationCode:
    """A temporary authorization code for the code grant flow."""
    code: str
    client_id: str
    user_id: str
    redirect_uri: str
    scopes: List[str]
    expires_at: float
    code_challenge: Optional[str] = None  # PKCE
    code_challenge_method: str = "S256"


@dataclass
class OAuthToken:
    """An issued OAuth token."""
    access_token: str
    token_type: str = "Bearer"
    expires_in: int = 3600
    refresh_token: Optional[str] = None
    scope: str = ""

    def to_dict(self) -> Dict:
        result = {
            "access_token": self.access_token,
            "token_type": self.token_type,
            "expires_in": self.expires_in,
            "scope": self.scope,
        }
        if self.refresh_token:
            result["refresh_token"] = self.refresh_token
        return result


class OAuthService:
    """OAuth 2.0 authorization server implementation."""

    def __init__(self):
        self._clients: Dict[str, OAuthClient] = {}
        self._auth_codes: Dict[str, AuthorizationCode] = {}
        self._tokens: Dict[str, Dict] = {}  # access_token -> token metadata
        self._refresh_tokens: Dict[str, Dict] = {}  # refresh_token -> metadata

    @staticmethod
    def _hash_secret(secret: str) -> str:
        return hashlib.sha256(secret.encode()).hexdigest()

    @staticmethod
    def _verify_pkce(code_verifier: str, code_challenge: str) -> bool:
        """Verify PKCE code_verifier against code_challenge (S256)."""
        computed = hashlib.sha256(code_verifier.encode()).hexdigest()
        return hmac.compare_digest(computed, code_challenge)

    async def register_client(
        self,
        name: str,
        org_id: str,
        redirect_uris: List[str],
        scopes: List[str],
        db=None,
    ) -> Dict:
        """Register a new OAuth client and return credentials."""
        client_id = f"nexus_{uuid.uuid4().hex[:16]}"
        client_secret = f"nxs_{secrets.token_urlsafe(32)}"

        client = OAuthClient(
            client_id=client_id,
            client_secret_hash=self._hash_secret(client_secret),
            client_name=name,
            org_id=org_id,
            redirect_uris=redirect_uris,
            allowed_scopes=scopes,
        )
        self._clients[client_id] = client

        if db:
            try:
                await db.table("oauth_clients").insert({
                    "client_id": client_id,
                    "client_secret_hash": client.client_secret_hash,
                    "client_name": name,
                    "org_id": org_id,
                    "redirect_uris": redirect_uris,
                    "allowed_scopes": scopes,
                    "is_active": True,
                }).execute()
            except Exception as e:
                logger.warning(f"Failed to persist OAuth client: {e}")

        return {
            "client_id": client_id,
            "client_secret": client_secret,  # Only returned at registration
            "client_name": name,
        }

    async def authorize(
        self,
        client_id: str,
        redirect_uri: str,
        scopes: List[str],
        user_id: str,
        code_challenge: str = None,
    ) -> Optional[AuthorizationCode]:
        """Generate an authorization code for the code grant flow."""
        client = self._clients.get(client_id)
        if not client or not client.is_active:
            return None

        if redirect_uri not in client.redirect_uris:
            return None

        # Validate requested scopes
        invalid_scopes = set(scopes) - set(client.allowed_scopes)
        if invalid_scopes:
            return None

        code = secrets.token_urlsafe(32)
        auth_code = AuthorizationCode(
            code=code,
            client_id=client_id,
            user_id=user_id,
            redirect_uri=redirect_uri,
            scopes=scopes,
            expires_at=time.time() + 600,  # 10 minute expiry
            code_challenge=code_challenge,
        )
        self._auth_codes[code] = auth_code
        return auth_code

    async def exchange_code(
        self,
        code: str,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        code_verifier: str = None,
    ) -> Optional[OAuthToken]:
        """Exchange an authorization code for tokens."""
        auth_code = self._auth_codes.pop(code, None)
        if not auth_code:
            return None

        # Validate
        if auth_code.client_id != client_id:
            return None
        if auth_code.redirect_uri != redirect_uri:
            return None
        if time.time() > auth_code.expires_at:
            return None

        # Verify client secret
        client = self._clients.get(client_id)
        if not client:
            return None
        if self._hash_secret(client_secret) != client.client_secret_hash:
            return None

        # PKCE verification
        if auth_code.code_challenge:
            if not code_verifier:
                return None
            if not self._verify_pkce(code_verifier, auth_code.code_challenge):
                return None

        # Generate tokens
        access_token = secrets.token_urlsafe(32)
        refresh_token = secrets.token_urlsafe(32)
        scope_str = " ".join(auth_code.scopes)

        token = OAuthToken(
            access_token=access_token,
            refresh_token=refresh_token,
            scope=scope_str,
        )

        self._tokens[access_token] = {
            "client_id": client_id,
            "user_id": auth_code.user_id,
            "scopes": auth_code.scopes,
            "expires_at": time.time() + 3600,
        }
        self._refresh_tokens[refresh_token] = {
            "client_id": client_id,
            "user_id": auth_code.user_id,
            "scopes": auth_code.scopes,
        }

        return token

    async def refresh_token(
        self, refresh_tok: str, client_id: str
    ) -> Optional[OAuthToken]:
        """Refresh an expired access token."""
        rt_data = self._refresh_tokens.get(refresh_tok)
        if not rt_data or rt_data["client_id"] != client_id:
            return None

        # Generate new access token
        new_access = secrets.token_urlsafe(32)
        new_refresh = secrets.token_urlsafe(32)

        self._tokens[new_access] = {
            "client_id": client_id,
            "user_id": rt_data["user_id"],
            "scopes": rt_data["scopes"],
            "expires_at": time.time() + 3600,
        }

        # Rotate refresh token
        del self._refresh_tokens[refresh_tok]
        self._refresh_tokens[new_refresh] = rt_data

        return OAuthToken(
            access_token=new_access,
            refresh_token=new_refresh,
            scope=" ".join(rt_data["scopes"]),
        )

    async def validate_token(self, access_token: str) -> Optional[Dict]:
        """Validate an access token and return its claims."""
        data = self._tokens.get(access_token)
        if not data:
            return None
        if time.time() > data.get("expires_at", 0):
            del self._tokens[access_token]
            return None
        return data

    async def revoke_token(self, token: str) -> bool:
        """Revoke an access or refresh token."""
        if token in self._tokens:
            del self._tokens[token]
            return True
        if token in self._refresh_tokens:
            del self._refresh_tokens[token]
            return True
        return False


# Global instance
oauth_service = OAuthService()
