"""Off-site storage for backup payloads.

Backups used to live only in ``backup_records.data`` - the same database they
protect. That survives an accidental row delete and nothing else. This module
adds a pluggable destination so `BACKUP_STORAGE_BACKEND` can move the payload
to a filesystem volume or an S3-compatible bucket, leaving only a manifest and
a checksum in the primary database.

Failure policy: an unusable backend raises :class:`BackupStorageUnavailableError`.
Callers must surface that instead of silently writing the payload back into the
primary database, because a "backup" that shares fate with the database is
worse than a visibly failing one.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import tempfile
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

logger = logging.getLogger(__name__)


class BackupStorageError(RuntimeError):
    """Base class for storage failures."""


class BackupStorageUnavailableError(BackupStorageError):
    """The configured destination cannot be used right now."""


def canonical_payload(payload: Any) -> bytes:
    """Serialize a payload deterministically so its checksum is stable."""
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")


def checksum_for(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True)
class StoredPayload:
    """Where a payload landed, and how to prove it later."""

    backend: str
    ref: str | None
    checksum: str
    size_bytes: int


class BackupStorage(Protocol):
    backend: str

    def store(
        self, *, org_id: str, label: str, payload: bytes, checksum: str
    ) -> str | None: ...

    def load(self, ref: str) -> bytes: ...

    def delete(self, ref: str) -> bool: ...

    def describe(self) -> dict[str, Any]: ...


def _object_name(org_id: str, label: str) -> str:
    """Build a collision-free object name.

    A timestamp alone is not enough: a manual backup and the ``pre_restore``
    backup taken during a restore can land in the same second, and the second
    write would silently overwrite the first object while both rows still
    reference it.
    """
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    safe_label = "".join(ch if ch.isalnum() or ch in "-_." else "-" for ch in label)
    return f"{org_id}/{stamp}-{safe_label}-{uuid.uuid4().hex[:8]}.json"


class DatabaseBackupStorage:
    """Legacy behaviour: the payload column is the destination."""

    backend = "database"

    def store(
        self, *, org_id: str, label: str, payload: bytes, checksum: str
    ) -> str | None:
        return None

    def load(self, ref: str) -> bytes:  # pragma: no cover - never reached
        raise BackupStorageError(
            "the database backend keeps payloads in backup_records.data"
        )

    def delete(self, ref: str) -> bool:
        return False

    def describe(self) -> dict[str, Any]:
        return {"backend": self.backend}


class FilesystemBackupStorage:
    """Write payloads to a mounted volume (NFS/PVC/attached disk)."""

    backend = "filesystem"

    def __init__(self, root: str) -> None:
        self._root = Path(root).expanduser()

    def _resolve(self, ref: str) -> Path:
        path = Path(ref)
        if not path.is_absolute():
            path = self._root / ref
        resolved = path.resolve()
        root = self._root.resolve()
        if root not in resolved.parents:
            raise BackupStorageError(f"ref escapes the backup root: {ref}")
        return resolved

    def store(self, *, org_id: str, label: str, payload: bytes, checksum: str) -> str:
        target = self._root / _object_name(org_id, label)
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            handle, temp_name = tempfile.mkstemp(dir=str(target.parent))
            temp_path = Path(temp_name)
            try:
                with os.fdopen(handle, "wb") as temp_file:
                    temp_file.write(payload)
                    temp_file.flush()
                    os.fsync(temp_file.fileno())
                os.replace(temp_name, target)
            finally:
                # No-op once os.replace() consumed the temporary file.
                temp_path.unlink(missing_ok=True)
        except OSError as exc:
            raise BackupStorageUnavailableError(
                f"filesystem backup storage unavailable at {self._root}: {exc}"
            ) from exc
        return str(target)

    def load(self, ref: str) -> bytes:
        path = self._resolve(ref)
        try:
            return path.read_bytes()
        except OSError as exc:
            raise BackupStorageUnavailableError(
                f"cannot read backup {path}: {exc}"
            ) from exc

    def delete(self, ref: str) -> bool:
        path = self._resolve(ref)
        try:
            path.unlink()
        except FileNotFoundError:
            return False
        except OSError as exc:
            raise BackupStorageUnavailableError(
                f"cannot delete backup {path}: {exc}"
            ) from exc
        return True

    def describe(self) -> dict[str, Any]:
        return {"backend": self.backend, "root": str(self._root)}


class S3BackupStorage:
    """Write payloads to an S3-compatible bucket (requires ``boto3``)."""

    backend = "s3"
    #: Populated in ``__init__`` so every method catches the provider error
    #: tree specifically rather than a broad ``Exception``.
    _client_errors: tuple[type[BaseException], ...] = ()

    def __init__(self, settings: Any) -> None:
        self._bucket = (getattr(settings, "BACKUP_S3_BUCKET", "") or "").strip()
        self._prefix = (getattr(settings, "BACKUP_S3_PREFIX", "") or "").strip("/")
        try:
            import boto3
            from botocore.exceptions import BotoCoreError, ClientError
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise BackupStorageUnavailableError(
                "BACKUP_STORAGE_BACKEND=s3 requires the boto3 package "
                "(pip install boto3)"
            ) from exc
        self._client_errors = (BotoCoreError, ClientError)
        if not self._bucket:
            raise BackupStorageUnavailableError(
                "BACKUP_STORAGE_BACKEND=s3 requires BACKUP_S3_BUCKET"
            )
        self._client = boto3.client(
            "s3",
            region_name=getattr(settings, "BACKUP_S3_REGION", "us-east-1"),
            endpoint_url=getattr(settings, "BACKUP_S3_ENDPOINT_URL", "") or None,
            aws_access_key_id=getattr(settings, "BACKUP_S3_ACCESS_KEY_ID", "") or None,
            aws_secret_access_key=(
                getattr(settings, "BACKUP_S3_SECRET_ACCESS_KEY", "") or None
            ),
        )

    def _key(self, name: str) -> str:
        return f"{self._prefix}/{name}" if self._prefix else name

    def store(self, *, org_id: str, label: str, payload: bytes, checksum: str) -> str:
        key = self._key(_object_name(org_id, label))
        try:
            self._client.put_object(
                Bucket=self._bucket,
                Key=key,
                Body=payload,
                ContentType="application/json",
                Metadata={"nexus-checksum": checksum},
            )
        except self._client_errors as exc:
            raise BackupStorageUnavailableError(
                f"cannot upload backup to s3://{self._bucket}/{key}: {exc}"
            ) from exc
        return f"s3://{self._bucket}/{key}"

    def load(self, ref: str) -> bytes:
        bucket, _, key = ref.removeprefix("s3://").partition("/")
        try:
            response = self._client.get_object(Bucket=bucket or self._bucket, Key=key)
            return response["Body"].read()
        except self._client_errors as exc:
            raise BackupStorageUnavailableError(
                f"cannot download backup {ref}: {exc}"
            ) from exc

    def delete(self, ref: str) -> bool:
        bucket, _, key = ref.removeprefix("s3://").partition("/")
        try:
            self._client.delete_object(Bucket=bucket or self._bucket, Key=key)
        except self._client_errors as exc:
            raise BackupStorageUnavailableError(
                f"cannot delete backup {ref}: {exc}"
            ) from exc
        return True

    def describe(self) -> dict[str, Any]:
        return {
            "backend": self.backend,
            "bucket": self._bucket,
            "prefix": self._prefix or None,
        }


def build_backup_storage(settings: Any) -> BackupStorage:
    """Build the configured storage, raising when the destination is unusable."""
    backend = (getattr(settings, "BACKUP_STORAGE_BACKEND", "database") or "").lower()
    if backend == "filesystem":
        return FilesystemBackupStorage(
            getattr(settings, "BACKUP_STORAGE_PATH", "/var/lib/nexus/backups")
        )
    if backend == "s3":
        return S3BackupStorage(settings)
    return DatabaseBackupStorage()
