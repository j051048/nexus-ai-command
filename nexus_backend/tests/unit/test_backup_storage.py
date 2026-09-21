"""Backup storage backends: checksums, off-site writes and failure modes."""

from __future__ import annotations

import sys
import types

import pytest

from app.services.backup_storage import (
    BackupStorageError,
    BackupStorageUnavailableError,
    DatabaseBackupStorage,
    FilesystemBackupStorage,
    S3BackupStorage,
    build_backup_storage,
    canonical_payload,
    checksum_for,
)


class _StubSettings:
    BACKUP_STORAGE_BACKEND = "filesystem"
    BACKUP_STORAGE_PATH = "/tmp/nexus-backups"
    BACKUP_S3_BUCKET = "nexus-backups"
    BACKUP_S3_PREFIX = "prefix"
    BACKUP_S3_REGION = "us-east-1"
    BACKUP_S3_ENDPOINT_URL = ""
    BACKUP_S3_ACCESS_KEY_ID = "key"
    BACKUP_S3_SECRET_ACCESS_KEY = "secret"


def test_canonical_payload_is_key_order_independent() -> None:
    left = canonical_payload({"b": 1, "a": {"y": 2, "x": 3}})
    right = canonical_payload({"a": {"x": 3, "y": 2}, "b": 1})

    assert left == right
    assert checksum_for(left) == checksum_for(right)
    assert checksum_for(left).startswith("sha256:")


def test_filesystem_backend_round_trip(tmp_path) -> None:
    storage = FilesystemBackupStorage(str(tmp_path))
    payload = canonical_payload({"customers": [{"id": "1"}]})
    checksum = checksum_for(payload)

    ref = storage.store(org_id="org-1", label="auto", payload=payload, checksum=checksum)

    assert ref.startswith(str(tmp_path))
    assert storage.load(ref) == payload
    assert storage.delete(ref) is True
    assert storage.delete(ref) is False


def test_filesystem_backend_stores_org_scoped_objects(tmp_path) -> None:
    storage = FilesystemBackupStorage(str(tmp_path))

    ref = storage.store(
        org_id="org-9", label="manual", payload=b"{}", checksum=checksum_for(b"{}")
    )

    assert str(tmp_path / "org-9") in ref


def test_filesystem_backend_rejects_refs_outside_the_root(tmp_path) -> None:
    storage = FilesystemBackupStorage(str(tmp_path / "root"))

    with pytest.raises(BackupStorageError):
        storage.load(str(tmp_path / "elsewhere.json"))


def test_filesystem_backend_reports_unavailable_target(tmp_path) -> None:
    blocked = tmp_path / "blocked"
    blocked.write_text("not a directory", encoding="utf-8")
    storage = FilesystemBackupStorage(str(blocked))

    with pytest.raises(BackupStorageUnavailableError):
        storage.store(org_id="org-1", label="auto", payload=b"{}", checksum="sha256:x")


def test_database_backend_keeps_payload_in_place() -> None:
    storage = DatabaseBackupStorage()

    assert storage.store(org_id="o", label="auto", payload=b"{}", checksum="c") is None
    assert storage.describe() == {"backend": "database"}


def test_factory_selects_filesystem_and_defaults_to_database() -> None:
    assert isinstance(build_backup_storage(_StubSettings()), FilesystemBackupStorage)

    class _Default(_StubSettings):
        BACKUP_STORAGE_BACKEND = "database"

    assert isinstance(build_backup_storage(_Default()), DatabaseBackupStorage)


def test_s3_backend_without_boto3_fails_loudly(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "boto3", None)
    monkeypatch.setitem(sys.modules, "botocore", None)
    monkeypatch.setitem(sys.modules, "botocore.exceptions", None)

    class _S3(_StubSettings):
        BACKUP_STORAGE_BACKEND = "s3"

    with pytest.raises(BackupStorageUnavailableError, match="boto3"):
        build_backup_storage(_S3())


def test_s3_backend_uploads_and_reads_back(monkeypatch) -> None:
    calls: dict[str, object] = {}

    class _Body:
        def read(self) -> bytes:
            return b'{"ok":true}'

    class _Client:
        def put_object(self, **kwargs):
            calls["put"] = kwargs
            return {}

        def get_object(self, **kwargs):
            calls["get"] = kwargs
            return {"Body": _Body()}

        def delete_object(self, **kwargs):
            calls["delete"] = kwargs
            return {}

    fake_boto3 = types.ModuleType("boto3")

    def _make_client(*_args, **kwargs):
        calls["client"] = kwargs
        return _Client()

    fake_boto3.client = _make_client
    fake_botocore = types.ModuleType("botocore")
    fake_exceptions = types.ModuleType("botocore.exceptions")

    class _BotoCoreError(Exception):
        pass

    class _ClientError(Exception):
        pass

    fake_exceptions.BotoCoreError = _BotoCoreError
    fake_exceptions.ClientError = _ClientError
    monkeypatch.setitem(sys.modules, "boto3", fake_boto3)
    monkeypatch.setitem(sys.modules, "botocore", fake_botocore)
    monkeypatch.setitem(sys.modules, "botocore.exceptions", fake_exceptions)

    class _S3(_StubSettings):
        BACKUP_STORAGE_BACKEND = "s3"

    storage = S3BackupStorage(_S3())
    ref = storage.store(org_id="org-1", label="auto", payload=b'{"a":1}', checksum="sha256:x")

    assert ref.startswith("s3://nexus-backups/prefix/org-1/")
    assert calls["put"]["Bucket"] == "nexus-backups"
    assert calls["put"]["Metadata"] == {"nexus-checksum": "sha256:x"}
    assert storage.load(ref) == b'{"ok":true}'
    assert storage.delete(ref) is True
    assert storage.describe() == {
        "backend": "s3",
        "bucket": "nexus-backups",
        "prefix": "prefix",
    }


def test_s3_backend_requires_a_bucket(monkeypatch) -> None:
    fake_boto3 = types.ModuleType("boto3")
    fake_boto3.client = lambda *args, **kwargs: object()
    fake_exceptions = types.ModuleType("botocore.exceptions")
    fake_exceptions.BotoCoreError = type("BotoCoreError", (Exception,), {})
    fake_exceptions.ClientError = type("ClientError", (Exception,), {})
    monkeypatch.setitem(sys.modules, "boto3", fake_boto3)
    monkeypatch.setitem(sys.modules, "botocore.exceptions", fake_exceptions)

    class _NoBucket(_StubSettings):
        BACKUP_STORAGE_BACKEND = "s3"
        BACKUP_S3_BUCKET = ""

    with pytest.raises(BackupStorageUnavailableError, match="BACKUP_S3_BUCKET"):
        S3BackupStorage(_NoBucket())
