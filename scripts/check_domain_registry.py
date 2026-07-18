#!/usr/bin/env python3
"""Validate gradual DDD ownership without forcing a risky big-bang rewrite."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "nexus_backend"
sys.path.insert(0, str(BACKEND))

from app.core.transaction_contracts import TRANSACTION_CONTRACTS  # noqa: E402
from app.domains import DOMAIN_REGISTRY  # noqa: E402

VALID_MATURITY = {"core", "supported", "emerging", "optional"}


def validate_registry(root: Path = ROOT) -> list[str]:
    failures: list[str] = []
    router_owners: dict[str, str] = {}

    for code, descriptor in DOMAIN_REGISTRY.items():
        if code != descriptor.code:
            failures.append(f"{code}: descriptor code is {descriptor.code}")
        if descriptor.owner == "unassigned":
            failures.append(f"{code}: owner is unassigned")
        if descriptor.maturity not in VALID_MATURITY:
            failures.append(f"{code}: invalid maturity {descriptor.maturity}")
        if descriptor.maturity == "core" and not descriptor.services:
            failures.append(f"{code}: core domain has no service ownership")

        for router in descriptor.routers:
            previous = router_owners.get(router)
            if previous:
                failures.append(
                    f"router {router} is owned by both {previous} and {code}"
                )
            router_owners[router] = code
            path = root / "nexus_backend" / "app" / "routers" / f"{router}.py"
            if not path.exists():
                failures.append(f"{code}: missing router module {router}")

        for service in descriptor.services:
            service_file = root / "nexus_backend" / "app" / "services" / f"{service}.py"
            service_package = root / "nexus_backend" / "app" / "services" / service
            if not service_file.exists() and not service_package.is_dir():
                failures.append(f"{code}: missing service module {service}")

    for contract in TRANSACTION_CONTRACTS:
        if contract.domain not in DOMAIN_REGISTRY:
            failures.append(
                f"transaction {contract.code} has no registered domain owner"
            )

    return failures


def main() -> int:
    failures = validate_registry()
    if failures:
        print("DOMAIN_REGISTRY_FAIL")
        for failure in failures:
            print(f" - {failure}")
        return 1
    print(
        "DOMAIN_REGISTRY_OK "
        f"domains={len(DOMAIN_REGISTRY)} routers={sum(len(d.routers) for d in DOMAIN_REGISTRY.values())}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
