from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.artifact_persistence import persist_artifact_package


@pytest.mark.asyncio
async def test_atomic_boundary_has_no_partial_write_fallback():
    db = MagicMock()
    db.rpc.return_value.execute = AsyncMock(side_effect=RuntimeError("transaction failed"))
    with pytest.raises(RuntimeError, match="transaction failed"):
        await persist_artifact_package(
            db, artifact={"id": "a", "organization_id": "org", "created_by": "u"},
            version={}, links=[], result={"id": "a"}, job_id="job", lease_token="lease",
        )
    db.table.assert_not_called()
    assert db.rpc.call_args.args[1]["p_lease_token"] == "lease"


@pytest.mark.asyncio
async def test_incomplete_lease_is_rejected_before_database_access():
    db = MagicMock()
    with pytest.raises(ValueError):
        await persist_artifact_package(db, artifact={}, version={}, links=[], result={}, job_id="job")
    db.rpc.assert_not_called()
