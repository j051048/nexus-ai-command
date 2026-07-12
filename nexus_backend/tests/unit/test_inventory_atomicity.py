from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.services.inventory_service import InventoryService


class AwaitableResult:
    def __init__(self, data):
        self.data = data

    def __await__(self):
        async def resolve():
            return self

        return resolve().__await__()


class FakeRPC:
    def __init__(self, data):
        self.data = data

    def execute(self):
        return AwaitableResult(self.data)


@pytest.mark.asyncio
async def test_inventory_in_uses_atomic_rpc():
    db = SimpleNamespace(rpc=MagicMock(return_value=FakeRPC({"new_quantity": 12})))
    result = await InventoryService().inventory_in(
        "00000000-0000-0000-0000-000000000001",
        "00000000-0000-0000-0000-000000000002",
        5,
        "00000000-0000-0000-0000-000000000003",
        db=db,
    )
    assert result["new_quantity"] == 12
    _, params = db.rpc.call_args.args
    assert params["p_delta"] == 5


@pytest.mark.asyncio
async def test_inventory_out_uses_negative_atomic_delta():
    db = SimpleNamespace(rpc=MagicMock(return_value=FakeRPC({"new_quantity": 7})))
    await InventoryService().inventory_out(
        "00000000-0000-0000-0000-000000000001",
        "00000000-0000-0000-0000-000000000002",
        5,
        "00000000-0000-0000-0000-000000000003",
        db=db,
    )
    _, params = db.rpc.call_args.args
    assert params["p_delta"] == -5


@pytest.mark.asyncio
async def test_inventory_rejects_non_positive_quantity():
    with pytest.raises(ValueError):
        await InventoryService().inventory_in("org", "item", 0, "user", db=object())
