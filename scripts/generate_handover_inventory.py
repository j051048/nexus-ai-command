#!/usr/bin/env python3
"""Generate a stable, reviewable inventory for engineering handover."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "handbook" / "generated" / "inventory.md"
IGNORED_PARTS = {
    ".git",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "coverage",
    "dist",
    "node_modules",
    "playwright-report",
    "test-results",
}


def source_files(path: Path, suffixes: set[str]) -> list[Path]:
    return sorted(
        item
        for item in path.rglob("*")
        if item.is_file()
        and item.suffix in suffixes
        and not any(part in IGNORED_PARTS for part in item.parts)
    )


def count_lines(files: list[Path]) -> int:
    total = 0
    for path in files:
        try:
            total += len(path.read_text(encoding="utf-8").splitlines())
        except UnicodeDecodeError:
            continue
    return total


def default_model() -> str:
    config = (ROOT / "nexus_backend" / "app" / "core" / "config.py").read_text(
        encoding="utf-8"
    )
    match = re.search(r'^FORCED_CHAT_MODEL\s*=\s*["\']([^"\']+)', config, re.MULTILINE)
    return match.group(1) if match else "未识别"


def render_inventory() -> str:
    frontend = source_files(ROOT / "src", {".ts", ".tsx"})
    backend = source_files(ROOT / "nexus_backend" / "app", {".py"})
    frontend_tests = source_files(ROOT / "src" / "__tests__", {".ts", ".tsx"})
    backend_tests = source_files(ROOT / "nexus_backend" / "tests", {".py"})
    e2e = source_files(ROOT / "e2e", {".ts", ".tsx"})
    routers = [
        path
        for path in source_files(ROOT / "nexus_backend" / "app" / "routers", {".py"})
        if path.name != "__init__.py"
    ]
    services = [
        path
        for path in source_files(ROOT / "nexus_backend" / "app" / "services", {".py"})
        if path.name != "__init__.py"
    ]
    tools = [
        path
        for path in source_files(ROOT / "nexus_backend" / "app" / "tools", {".py"})
        if path.name != "__init__.py"
    ]
    pages = source_files(ROOT / "src" / "pages", {".ts", ".tsx"})
    migration_root = ROOT / "supabase" / "migrations"
    migrations = sorted(
        path
        for path in migration_root.glob("*.sql")
        if path.name != "machine_generated_master_setup.sql"
    )
    rollback_migrations = source_files(migration_root / "rollback", {".sql"})

    largest = sorted(
        ((len(path.read_text(encoding="utf-8").splitlines()), path) for path in frontend),
        reverse=True,
    )[:10]
    largest_rows = "\n".join(
        f"| `{path.relative_to(ROOT).as_posix()}` | {lines} |" for lines, path in largest
    )

    return f"""# 工程事实清单

> 本文件由 `python scripts/generate_handover_inventory.py` 生成。不要手工修改。

## 规模

| 范围 | 文件数 | 代码行数 |
|---|---:|---:|
| 前端 `src` | {len(frontend)} | {count_lines(frontend)} |
| 后端 `nexus_backend/app` | {len(backend)} | {count_lines(backend)} |
| 前端单元/集成测试 | {len(frontend_tests)} | {count_lines(frontend_tests)} |
| 后端测试 | {len(backend_tests)} | {count_lines(backend_tests)} |
| Playwright E2E | {len(e2e)} | {count_lines(e2e)} |

## 运行时资产

| 资产 | 数量/值 | 权威来源 |
|---|---:|---|
| 前端页面文件 | {len(pages)} | `src/pages` |
| FastAPI 路由模块 | {len(routers)} | `nexus_backend/app/routers` |
| 后端服务模块 | {len(services)} | `nexus_backend/app/services` |
| Agent 工具模块 | {len(tools)} | `nexus_backend/app/tools` |
| 正向 SQL 迁移 | {len(migrations)} | `supabase/migrations/*.sql` |
| 回滚 SQL | {len(rollback_migrations)} | `supabase/migrations/rollback` |
| 强制生产聊天模型 | `{default_model()}` | `nexus_backend/app/core/config.py` |

## 前端最大文件

这些文件是渐进拆分清单，不代表可以无测试地批量重写。

| 文件 | 行数 |
|---|---:|
{largest_rows}
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="Fail when inventory is stale")
    args = parser.parse_args()
    rendered = render_inventory()
    if args.check:
        if not OUTPUT.exists() or OUTPUT.read_text(encoding="utf-8") != rendered:
            print("HANDOVER_INVENTORY_STALE")
            return 1
        print("HANDOVER_INVENTORY_OK")
        return 0
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(rendered, encoding="utf-8")
    print(f"Wrote {OUTPUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
