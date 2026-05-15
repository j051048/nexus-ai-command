"""Static customer acceptance gate for the small-company launch profile."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class LaunchModule:
    flag: str
    route: str
    owner: str
    backend_files: tuple[str, ...]


SMALL_COMPANY_MODULES = [
    LaunchModule("crm", "/crm", "sales", ("nexus_backend/app/routers/crm.py",)),
    LaunchModule("approval", "/approval", "workflow", ("nexus_backend/app/routers/approval.py",)),
    LaunchModule("documents", "/documents", "knowledge", ("nexus_backend/app/routers/documents.py",)),
    LaunchModule("knowledge", "/knowledge", "knowledge", ("nexus_backend/app/routers/memories.py",)),
    LaunchModule("finance", "/finance", "finance", ("nexus_backend/app/routers/finance.py",)),
    LaunchModule("hr", "/hr", "people", ("nexus_backend/app/routers/hr.py",)),
    LaunchModule("oa", "/oa", "workflow", ("nexus_backend/app/routers/oa.py",)),
    LaunchModule("projects", "/projects", "delivery", ("nexus_backend/app/routers/projects.py",)),
    LaunchModule("reports", "/reports", "analytics", ("nexus_backend/app/routers/reports.py",)),
    LaunchModule("vmd", "/vmd", "marketing", ("nexus_backend/app/routers/vmd_dashboard.py",)),
    LaunchModule("plugins", "/plugins", "platform", ("nexus_backend/app/routers/plugins.py",)),
    LaunchModule("workflow_designer", "/workflows", "workflow", ("nexus_backend/app/routers/workflows.py",)),
]

SAFETY_FILES = {
    "Tool RBAC": ("nexus_backend/app/core/tool_rbac.py", ("Deny-by-default guard", "ROLE_DENY_LIST")),
    "Idempotency": ("nexus_backend/app/core/idempotency_middleware.py", ("X-Idempotency-Key", "IDEMPOTENCY_MEMORY_FALLBACK_MAX")),
    "Audit Logger": ("nexus_backend/app/services/audit_logger.py", ("AuditLogger", "_sanitize")),
    "Irreversible HITL": (
        "nexus_backend/app/agent/safety_guards.py",
        ("is_irreversible", "check_approval_needed", "ApprovalScope.ONCE"),
    ),
    "API Key Hard Fail": ("nexus_backend/app/core/api_key_middleware.py", ("never silently downgraded", "Invalid API key")),
}


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8", errors="replace")


def exists(path: str) -> bool:
    return (ROOT / path).exists()


def main() -> int:
    failures: list[str] = []
    feature_flags = read("src/config/featureFlags.ts")
    readiness = read("src/config/customerLaunchModules.ts")
    smoke = read("e2e/top10-critical-flows.spec.ts")
    env_example = read(".env.production.example")

    print("Customer acceptance gate: small_company launch profile")
    if "SMALL_COMPANY_LAUNCH_MODULES" not in feature_flags:
        failures.append("featureFlags.ts must define SMALL_COMPANY_LAUNCH_MODULES")
    if "VITE_LAUNCH_PROFILE=small_company" not in env_example:
        failures.append(".env.production.example must default to VITE_LAUNCH_PROFILE=small_company")

    for module in SMALL_COMPANY_MODULES:
        module_ok = True
        for token in [f'"{module.flag}"', f'smokePath: "{module.route}"', f'owner: "{module.owner}"']:
            if token not in readiness and token not in feature_flags:
                failures.append(f"{module.flag}: missing {token}")
                module_ok = False
        if module.route not in smoke:
            failures.append(f"{module.flag}: route {module.route} missing from critical smoke suite")
            module_ok = False
        for backend_file in module.backend_files:
            if not exists(backend_file):
                failures.append(f"{module.flag}: backend file missing {backend_file}")
                module_ok = False
        print(f"{'OK' if module_ok else 'FAIL'} module {module.flag} -> {module.route}")

    for name, (path, tokens) in SAFETY_FILES.items():
        if not exists(path):
            failures.append(f"{name}: missing {path}")
            print(f"FAIL safety {name}")
            continue
        content = read(path)
        missing = [token for token in tokens if token not in content]
        if missing:
            failures.append(f"{name}: missing tokens {', '.join(missing)}")
            print(f"FAIL safety {name}")
        else:
            print(f"OK safety {name}")

    if failures:
        print("")
        print(f"Summary: {len(failures)} failure(s)")
        for failure in failures:
            print(f" - {failure}")
        return 1
    print("")
    print("Summary: customer acceptance gate passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
