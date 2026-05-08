"""Enterprise SSO helpers for OIDC and SAML callbacks.

The service is intentionally provider-agnostic. Provider settings are read from
environment variables so enterprise SSO can be enabled without a schema lock-in:

SSO_<PROVIDER>_AUTHORIZATION_ENDPOINT
SSO_<PROVIDER>_TOKEN_ENDPOINT
SSO_<PROVIDER>_CLIENT_ID
SSO_<PROVIDER>_CLIENT_SECRET
SSO_<PROVIDER>_ISSUER
SSO_<PROVIDER>_JWKS_URL
SSO_<PROVIDER>_SCOPES
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
import urllib.parse
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Any

import httpx
import jwt
from jwt import PyJWKClient


class EnterpriseSSOError(ValueError):
    """Raised when SSO input or provider configuration is invalid."""


@dataclass(frozen=True)
class OIDCProviderConfig:
    provider_code: str
    authorization_endpoint: str
    token_endpoint: str
    client_id: str
    client_secret: str
    issuer: str | None = None
    jwks_url: str | None = None
    scopes: str = "openid email profile"


class EnterpriseSSOService:
    """OIDC/SAML bootstrap with signed state and strict callback checks."""

    def __init__(self, state_secret: str | None = None):
        self.state_secret = state_secret or os.getenv("SSO_STATE_SECRET") or os.getenv("JWT_SECRET") or "dev-only-sso-state"
        self.state_ttl_seconds = int(os.getenv("SSO_STATE_TTL_SECONDS", "600"))

    def build_oidc_login_url(
        self,
        *,
        org_id: str,
        provider_code: str,
        redirect_uri: str,
        nonce: str,
    ) -> dict[str, str]:
        provider = self._load_oidc_provider(provider_code)
        state = self.sign_state(
            {
                "org_id": org_id,
                "provider_code": provider.provider_code,
                "redirect_uri": redirect_uri,
                "nonce": nonce,
            }
        )
        query = urllib.parse.urlencode(
            {
                "client_id": provider.client_id,
                "redirect_uri": redirect_uri,
                "response_type": "code",
                "scope": provider.scopes,
                "state": state,
                "nonce": nonce,
            }
        )
        return {
            "authorization_url": f"{provider.authorization_endpoint}?{query}",
            "state": state,
        }

    async def exchange_oidc_code(
        self,
        *,
        code: str,
        state: str,
        redirect_uri: str,
    ) -> dict[str, Any]:
        state_payload = self.verify_state(state)
        if state_payload.get("redirect_uri") != redirect_uri:
            raise EnterpriseSSOError("OIDC redirect_uri mismatch")

        provider = self._load_oidc_provider(str(state_payload["provider_code"]))
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                provider.token_endpoint,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "client_id": provider.client_id,
                    "client_secret": provider.client_secret,
                },
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            token_payload = response.json()

        id_token = token_payload.get("id_token")
        if not id_token:
            raise EnterpriseSSOError("OIDC provider did not return id_token")

        claims = self.verify_oidc_id_token(provider, id_token, nonce=state_payload.get("nonce"))
        return {
            "org_id": state_payload["org_id"],
            "provider_code": provider.provider_code,
            "claims": claims,
            "access_token": token_payload.get("access_token"),
            "expires_in": token_payload.get("expires_in"),
        }

    def verify_oidc_id_token(
        self,
        provider: OIDCProviderConfig,
        id_token: str,
        *,
        nonce: str | None = None,
    ) -> dict[str, Any]:
        if provider.jwks_url:
            signing_key = PyJWKClient(provider.jwks_url, cache_keys=True, lifespan=600).get_signing_key_from_jwt(id_token)
            claims = jwt.decode(
                id_token,
                signing_key.key,
                algorithms=["RS256", "ES256"],
                audience=provider.client_id,
                issuer=provider.issuer,
                options={"require": ["sub", "exp"]},
            )
        else:
            if os.getenv("SSO_ALLOW_UNVERIFIED_OIDC", "false").lower() != "true":
                raise EnterpriseSSOError("OIDC JWKS URL is required unless SSO_ALLOW_UNVERIFIED_OIDC=true")
            claims = jwt.decode(
                id_token,
                options={"verify_signature": False, "verify_aud": False, "verify_exp": True},
            )
            if provider.issuer and claims.get("iss") != provider.issuer:
                raise EnterpriseSSOError("OIDC issuer mismatch")
            if claims.get("aud") not in (provider.client_id, [provider.client_id]):
                raise EnterpriseSSOError("OIDC audience mismatch")

        if nonce and claims.get("nonce") and claims.get("nonce") != nonce:
            raise EnterpriseSSOError("OIDC nonce mismatch")
        return claims

    def parse_saml_response(self, saml_response_b64: str) -> dict[str, Any]:
        xml_bytes = base64.b64decode(saml_response_b64)
        root = ET.fromstring(xml_bytes)
        has_signature = root.find(".//{http://www.w3.org/2000/09/xmldsig#}Signature") is not None
        if not has_signature and os.getenv("SSO_ALLOW_UNSIGNED_SAML", "false").lower() != "true":
            raise EnterpriseSSOError("Unsigned SAML response rejected")

        ns = {
            "saml": "urn:oasis:names:tc:SAML:2.0:assertion",
        }
        name_id = root.find(".//saml:Subject/saml:NameID", ns)
        attributes: dict[str, str] = {}
        for attr in root.findall(".//saml:Attribute", ns):
            name = attr.attrib.get("Name")
            value = attr.find("saml:AttributeValue", ns)
            if name and value is not None and value.text:
                attributes[name] = value.text

        if name_id is None or not name_id.text:
            raise EnterpriseSSOError("SAML response missing NameID")

        return {
            "subject": name_id.text,
            "attributes": attributes,
            "signature_present": has_signature,
        }

    def sign_state(self, payload: dict[str, Any]) -> str:
        body = {**payload, "iat": int(time.time())}
        raw = self._b64(json.dumps(body, separators=(",", ":"), sort_keys=True).encode())
        signature = hmac.new(self.state_secret.encode(), raw.encode(), hashlib.sha256).digest()
        return f"{raw}.{self._b64(signature)}"

    def verify_state(self, state: str) -> dict[str, Any]:
        try:
            raw, sig = state.split(".", 1)
        except ValueError:
            raise EnterpriseSSOError("Invalid SSO state format")

        expected = self._b64(hmac.new(self.state_secret.encode(), raw.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(sig, expected):
            raise EnterpriseSSOError("Invalid SSO state signature")

        payload = json.loads(base64.urlsafe_b64decode(self._pad(raw)).decode())
        if int(time.time()) - int(payload.get("iat", 0)) > self.state_ttl_seconds:
            raise EnterpriseSSOError("SSO state expired")
        return payload

    def _load_oidc_provider(self, provider_code: str) -> OIDCProviderConfig:
        prefix = f"SSO_{provider_code.upper()}_"
        required = {
            "authorization_endpoint": os.getenv(prefix + "AUTHORIZATION_ENDPOINT"),
            "token_endpoint": os.getenv(prefix + "TOKEN_ENDPOINT"),
            "client_id": os.getenv(prefix + "CLIENT_ID"),
            "client_secret": os.getenv(prefix + "CLIENT_SECRET"),
        }
        missing = [key for key, value in required.items() if not value]
        if missing:
            raise EnterpriseSSOError(f"OIDC provider {provider_code} missing settings: {', '.join(missing)}")
        return OIDCProviderConfig(
            provider_code=provider_code,
            authorization_endpoint=str(required["authorization_endpoint"]),
            token_endpoint=str(required["token_endpoint"]),
            client_id=str(required["client_id"]),
            client_secret=str(required["client_secret"]),
            issuer=os.getenv(prefix + "ISSUER"),
            jwks_url=os.getenv(prefix + "JWKS_URL"),
            scopes=os.getenv(prefix + "SCOPES", "openid email profile"),
        )

    @staticmethod
    def _b64(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).decode().rstrip("=")

    @staticmethod
    def _pad(value: str) -> bytes:
        return (value + "=" * (-len(value) % 4)).encode()


enterprise_sso_service = EnterpriseSSOService()
