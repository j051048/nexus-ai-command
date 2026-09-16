import asyncio

import pytest

from app.core.tenant_throttle import TenantThrottle


async def _use(throttle, tenant):
    async with throttle.acquire(tenant):
        return tenant


@pytest.mark.asyncio
async def test_cancelled_waiter_does_not_leak_slot():
    throttle = TenantThrottle(1, 2)
    async with throttle.acquire("a"):
        pending = asyncio.create_task(_use(throttle, "a"))
        await asyncio.sleep(0)
        pending.cancel()
        with pytest.raises(asyncio.CancelledError):
            await pending
        assert throttle.get_stats()["total_queued"] == 0
    assert await asyncio.wait_for(_use(throttle, "a"), 1) == "a"
    assert throttle.get_stats()["total_active"] == 0


@pytest.mark.asyncio
async def test_tenant_queue_does_not_consume_global_capacity():
    throttle = TenantThrottle(1, 2)
    async with throttle.acquire("a"):
        pending = asyncio.create_task(_use(throttle, "a"))
        await asyncio.sleep(0)
        assert await asyncio.wait_for(_use(throttle, "b"), 1) == "b"
    await pending
    assert throttle.get_stats()["global_active"] == 0


@pytest.mark.asyncio
async def test_cancel_after_grant_returns_reserved_slot():
    throttle = TenantThrottle(1, 1)
    await throttle._wait_for_slot("a")
    pending = asyncio.create_task(_use(throttle, "b"))
    await asyncio.sleep(0)
    await throttle._release_slot("a")
    pending.cancel()
    with pytest.raises(asyncio.CancelledError):
        await pending
    assert throttle.get_stats()["global_active"] == 0
    assert await asyncio.wait_for(_use(throttle, "b"), 1) == "b"


@pytest.mark.asyncio
async def test_queue_timeout_cleans_up_and_global_limit_is_respected():
    throttle = TenantThrottle(2, 1, queue_timeout=0.01)
    async with throttle.acquire("a"):
        with pytest.raises(TimeoutError):
            await _use(throttle, "b")
        assert throttle.get_stats()["total_active"] == 1
        assert throttle.get_stats()["total_queued"] == 0
    assert throttle.get_stats()["total_active"] == 0
