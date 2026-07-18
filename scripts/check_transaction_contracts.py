#!/usr/bin/env python3
"""Verify that critical cross-table operations remain atomic and replay-safe."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "nexus_backend"
sys.path.insert(0, str(BACKEND))

from app.core.transaction_contracts import (  # noqa: E402
    TRANSACTION_CONTRACTS,
    ReplayStrategy,
)
from app.domains import DOMAIN_REGISTRY  # noqa: E402


def validate_contracts(root: Path = ROOT) -> list[str]:
    failures: list[str] = []
    codes: set[str] = set()
    rpc_names: set[str] = set()

    for contract in TRANSACTION_CONTRACTS:
        if contract.code in codes:
            failures.append(f"duplicate contract code: {contract.code}")
        codes.add(contract.code)
        if contract.rpc_name in rpc_names:
            failures.append(f"duplicate RPC contract: {contract.rpc_name}")
        rpc_names.add(contract.rpc_name)
        if contract.domain not in DOMAIN_REGISTRY:
            failures.append(
                f"{contract.code}: unknown domain ownership {contract.domain}"
            )

        migration = root / contract.migration
        caller = root / contract.caller
        if not migration.exists():
            failures.append(f"{contract.code}: missing migration {contract.migration}")
            continue
        if not caller.exists():
            failures.append(f"{contract.code}: missing caller {contract.caller}")
            continue

        sql = migration.read_text(encoding="utf-8", errors="replace")
        source = caller.read_text(encoding="utf-8", errors="replace")
        signature = f"FUNCTION public.{contract.rpc_name}"
        if signature not in sql:
            failures.append(f"{contract.code}: migration does not define {signature}")
        if contract.security_mode not in sql:
            failures.append(
                f"{contract.code}: missing security mode {contract.security_mode}"
            )
        for token in contract.required_sql_tokens:
            if token not in sql:
                failures.append(f"{contract.code}: SQL missing token {token!r}")
        for token in contract.required_caller_tokens:
            if token not in source:
                failures.append(f"{contract.code}: caller missing token {token!r}")
        for entrypoint in contract.entrypoints:
            entrypoint_path = root / entrypoint.path
            if not entrypoint_path.exists():
                failures.append(
                    f"{contract.code}: missing entrypoint {entrypoint.path}"
                )
                continue
            entrypoint_source = entrypoint_path.read_text(
                encoding="utf-8", errors="replace"
            )
            for token in entrypoint.required_tokens:
                if token not in entrypoint_source:
                    failures.append(
                        f"{contract.code}: entrypoint {entrypoint.path} "
                        f"missing token {token!r}"
                    )

        if contract.replay_strategy == ReplayStrategy.IDEMPOTENCY_KEY:
            parameter = contract.idempotency_parameter
            if not parameter:
                failures.append(f"{contract.code}: idempotency parameter is required")
            elif parameter not in sql or parameter not in source:
                failures.append(
                    f"{contract.code}: idempotency parameter {parameter} is not end-to-end"
                )
        elif "FOR UPDATE" not in sql:
            failures.append(
                f"{contract.code}: terminal-state replay guard requires a row lock"
            )

    return failures


def main() -> int:
    failures = validate_contracts()
    if failures:
        print("TRANSACTION_CONTRACTS_FAIL")
        for failure in failures:
            print(f" - {failure}")
        return 1
    print(f"TRANSACTION_CONTRACTS_OK count={len(TRANSACTION_CONTRACTS)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
