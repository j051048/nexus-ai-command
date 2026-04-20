"""Token 计费并发原子性测试

验证 TenantCreditService 在高并发下的扣费精确性:
1. 精确余额 — N 协程并发扣费，总 used 精确
2. 超额竞态 — 余额只够一半，恰好半数成功
3. 混合 credit_type — 不同类型互不干扰
4. RPC 原子性 — 绕过 asyncio.Lock，验证 DB 层兜底
5. 余额不能变负
"""

import asyncio
from dataclasses import dataclass, field

import pytest

from app.services.tenant_credit_service import (
    CreditType,
    TenantCreditService,
    TenantCredit,
)


# ─── AtomicRpcMock: 模拟 PG consume_tenant_credit 的原子语义 ──────────────


@dataclass
class _CreditState:
    allocated: int = 0
    used: int = 0
    reserved: int = 0

    @property
    def remaining(self) -> int:
        return self.allocated - self.used - self.reserved


class _MockResponse:
    def __init__(self, data):
        self.data = data
        self.error = None
        self.count = None


class _MockRpcCall:
    def __init__(self, data):
        self._data = data

    async def execute(self):
        return _MockResponse(self._data)


class AtomicRpcMock:
    """模拟 consume_tenant_credit RPC 的原子语义。
    用 asyncio.Lock 模拟 PG 行锁，确保 UPDATE ... RETURNING 的原子性。
    """

    def __init__(self):
        self._states: dict[tuple[str, str], _CreditState] = {}
        self._locks: dict[tuple[str, str], asyncio.Lock] = {}

    def seed(self, org_id: str, credit_type: str, allocated: int = 0, used: int = 0):
        key = (org_id, credit_type)
        self._states[key] = _CreditState(allocated=allocated, used=used)
        self._locks[key] = asyncio.Lock()

    def get_state(self, org_id: str, credit_type: str) -> _CreditState:
        return self._states[(org_id, credit_type)]

    def rpc(self, func_name: str, params: dict):
        if func_name != "consume_tenant_credit":
            return _MockRpcCall([])

        org_id = params["p_org_id"]
        credit_type = params["p_credit_type"]
        amount = params["p_amount"]
        key = (org_id, credit_type)

        async def _atomic_execute():
            lock = self._locks.get(key)
            if not lock:
                return _MockResponse([{"success": False, "remaining": 0}])
            async with lock:
                state = self._states[key]
                if state.remaining >= amount:
                    state.used += amount
                    return _MockResponse(
                        [{"success": True, "remaining": state.remaining}]
                    )
                return _MockResponse(
                    [{"success": False, "remaining": state.remaining}]
                )

        class _DeferredRpc:
            async def execute(self_inner):
                return await _atomic_execute()

        return _DeferredRpc()


# ─── Fixtures ────────────────────────────────────────────────────────────


@pytest.fixture
def credit_service():
    return TenantCreditService()


@pytest.fixture
def rpc_mock():
    return AtomicRpcMock()


def _seed_service(service: TenantCreditService, org_id: str, credit_type: CreditType,
                  allocated: int, used: int = 0):
    """Seed the in-memory cache of a TenantCreditService."""
    cache_key = f"{org_id}:{credit_type.value}"
    service._credit_cache[cache_key] = TenantCredit(
        org_id=org_id,
        credit_type=credit_type,
        allocated=allocated,
        used=used,
        reserved=0,
    )


# ─── 场景 1: 精确余额验证 ────────────────────────────────────────────────


class TestPreciseBalance:

    @pytest.mark.asyncio
    async def test_10_coroutines_exact_total(self, credit_service):
        """10 协程各消费 10 token，总 used 必须精确 100。"""
        org = "org-precise"
        _seed_service(credit_service, org, CreditType.TOKENS, allocated=1000)

        results = await asyncio.gather(
            *[credit_service.consume_credit(org, CreditType.TOKENS, 10) for _ in range(10)]
        )
        successes = [r for r in results if r[0]]
        assert len(successes) == 10

        cache_key = f"{org}:{CreditType.TOKENS.value}"
        credit = credit_service._credit_cache[cache_key]
        assert credit.used == 100

    @pytest.mark.asyncio
    async def test_100_coroutines_exact_total(self, credit_service):
        """100 协程各消费 1 token，总 used 必须精确 100。"""
        org = "org-precise-100"
        _seed_service(credit_service, org, CreditType.TOKENS, allocated=10000)

        results = await asyncio.gather(
            *[credit_service.consume_credit(org, CreditType.TOKENS, 1) for _ in range(100)]
        )
        successes = [r for r in results if r[0]]
        assert len(successes) == 100

        cache_key = f"{org}:{CreditType.TOKENS.value}"
        assert credit_service._credit_cache[cache_key].used == 100


# ─── 场景 2: 超额竞态 ───────────────────────────────────────────────────


class TestOverdraftRace:

    @pytest.mark.asyncio
    async def test_half_succeed_half_fail(self, credit_service):
        """余额 50，10 协程各扣 10 → 恰好 5 成功，used == 50。"""
        org = "org-overdraft"
        _seed_service(credit_service, org, CreditType.TOKENS, allocated=50)

        results = await asyncio.gather(
            *[credit_service.consume_credit(org, CreditType.TOKENS, 10) for _ in range(10)]
        )
        successes = sum(1 for r in results if r[0])
        failures = sum(1 for r in results if not r[0])

        assert successes == 5
        assert failures == 5

        cache_key = f"{org}:{CreditType.TOKENS.value}"
        assert credit_service._credit_cache[cache_key].used == 50

    @pytest.mark.asyncio
    async def test_uneven_amounts(self, credit_service):
        """余额 100，20 协程各扣 7 → 最多 14 个成功（14*7=98），used <= 100。"""
        org = "org-uneven"
        _seed_service(credit_service, org, CreditType.TOKENS, allocated=100)

        results = await asyncio.gather(
            *[credit_service.consume_credit(org, CreditType.TOKENS, 7) for _ in range(20)]
        )
        successes = sum(1 for r in results if r[0])
        cache_key = f"{org}:{CreditType.TOKENS.value}"
        used = credit_service._credit_cache[cache_key].used

        assert successes <= 14
        assert used <= 100
        assert used == successes * 7


# ─── 场景 3: 混合 credit_type 并发 ──────────────────────────────────────


class TestMixedCreditTypes:

    @pytest.mark.asyncio
    async def test_token_and_api_call_independent(self, credit_service):
        """TOKEN 和 API_CALL 同时并发扣费，互不干扰。"""
        org = "org-mixed"
        _seed_service(credit_service, org, CreditType.TOKENS, allocated=100)
        _seed_service(credit_service, org, CreditType.API_CALLS, allocated=50)

        token_tasks = [
            credit_service.consume_credit(org, CreditType.TOKENS, 10) for _ in range(10)
        ]
        api_tasks = [
            credit_service.consume_credit(org, CreditType.API_CALLS, 10) for _ in range(10)
        ]

        results = await asyncio.gather(*(token_tasks + api_tasks))
        token_results = results[:10]
        api_results = results[10:]

        token_ok = sum(1 for r in token_results if r[0])
        api_ok = sum(1 for r in api_results if r[0])

        assert token_ok == 10  # 100 / 10 = 10 all succeed
        assert api_ok == 5     # 50 / 10 = 5 succeed

        assert credit_service._credit_cache[f"{org}:{CreditType.TOKENS.value}"].used == 100
        assert credit_service._credit_cache[f"{org}:{CreditType.API_CALLS.value}"].used == 50


# ─── 场景 4: RPC 原子性（绕过 asyncio.Lock） ────────────────────────────


class TestRpcAtomicity:

    @pytest.mark.asyncio
    async def test_rpc_atomic_deduct(self, rpc_mock):
        """绕过 Python 锁，直接并发调用 RPC mock，验证 DB 层原子性。"""
        rpc_mock.seed("org-rpc", "tokens", allocated=50)

        async def call_rpc():
            resp = await rpc_mock.rpc("consume_tenant_credit", {
                "p_org_id": "org-rpc",
                "p_credit_type": "tokens",
                "p_amount": 10,
                "p_user_id": "user-1",
            }).execute()
            return resp.data[0]["success"]

        results = await asyncio.gather(*[call_rpc() for _ in range(10)])
        successes = sum(1 for r in results if r)

        assert successes == 5
        assert rpc_mock.get_state("org-rpc", "tokens").used == 50

    @pytest.mark.asyncio
    async def test_rpc_with_service_persist(self, credit_service, rpc_mock):
        """通过 service._persist_credit_usage 调用 RPC，验证端到端。"""
        rpc_mock.seed("org-persist", "tokens", allocated=100)
        _seed_service(credit_service, "org-persist", CreditType.TOKENS, allocated=100)

        async def persist_one():
            await credit_service._persist_credit_usage(
                "org-persist", CreditType.TOKENS, 10, "user-1", db=rpc_mock
            )

        await asyncio.gather(*[persist_one() for _ in range(10)])

        state = rpc_mock.get_state("org-persist", "tokens")
        assert state.used == 100
        assert state.remaining == 0


# ─── 场景 5: 余额不能变负 ───────────────────────────────────────────────


class TestNoNegativeBalance:

    @pytest.mark.asyncio
    async def test_balance_never_negative_service(self, credit_service):
        """allocated=15, 3 协程各扣 7 → 最多 2 成功, used <= 14。"""
        org = "org-neg"
        _seed_service(credit_service, org, CreditType.TOKENS, allocated=15)

        results = await asyncio.gather(
            *[credit_service.consume_credit(org, CreditType.TOKENS, 7) for _ in range(3)]
        )
        successes = sum(1 for r in results if r[0])
        cache_key = f"{org}:{CreditType.TOKENS.value}"
        used = credit_service._credit_cache[cache_key].used

        assert successes <= 2
        assert used <= 14
        assert used >= 0

    @pytest.mark.asyncio
    async def test_balance_never_negative_rpc(self, rpc_mock):
        """RPC 层: allocated=15, 3 协程各扣 7 → 最多 2 成功。"""
        rpc_mock.seed("org-neg-rpc", "tokens", allocated=15)

        async def call_rpc():
            resp = await rpc_mock.rpc("consume_tenant_credit", {
                "p_org_id": "org-neg-rpc",
                "p_credit_type": "tokens",
                "p_amount": 7,
                "p_user_id": "user-1",
            }).execute()
            return resp.data[0]["success"]

        results = await asyncio.gather(*[call_rpc() for _ in range(3)])
        successes = sum(1 for r in results if r)
        state = rpc_mock.get_state("org-neg-rpc", "tokens")

        assert successes <= 2
        assert state.used <= 14
        assert state.remaining >= 0
