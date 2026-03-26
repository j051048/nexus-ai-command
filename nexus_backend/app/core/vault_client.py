"""HashiCorp Vault 密钥管理"""
import os
import hvac
from typing import Optional

class VaultClient:
    def __init__(self):
        self.client = hvac.Client(
            url=os.getenv("VAULT_ADDR", "http://localhost:8200"),
            token=os.getenv("VAULT_TOKEN")
        )
    
    def get_secret(self, path: str) -> Optional[dict]:
        try:
            response = self.client.secrets.kv.v2.read_secret_version(path=path)
            return response["data"]["data"]
        except Exception:
            return None
    
    def set_secret(self, path: str, data: dict):
        self.client.secrets.kv.v2.create_or_update_secret(path=path, secret=data)

vault_client = VaultClient()
