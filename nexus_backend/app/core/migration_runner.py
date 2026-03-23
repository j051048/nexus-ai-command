"""
#18: 数据库迁移自动执行

在应用启动时检查并自动执行未应用的 SQL 迁移文件。
通过 migration_history 表记录已应用的迁移。

配置:
- AUTO_MIGRATE=true 环境变量启用自动迁移（默认关闭）
- 主迁移目录: nexus_backend/supabase_migrations/migrations/
- 同时扫描: supabase/migrations/ 和 nexus_backend/supabase/migrations/
  (Items 9/23: 统一扫描所有迁移目录，避免遗漏)
"""

import logging
import os
import re
from pathlib import Path

logger = logging.getLogger(__name__)

# 项目根目录
_PROJECT_ROOT = Path(__file__).parent.parent.parent

# 迁移文件目录 — 统一扫描所有3个历史目录 (Item 9/23)
MIGRATIONS_DIRS = [
    _PROJECT_ROOT / "supabase_migrations" / "migrations",  # 主目录 (52 files)
    _PROJECT_ROOT.parent / "supabase" / "migrations",      # 顶层 supabase (25 files)
    _PROJECT_ROOT / "supabase" / "migrations",             # 后端 supabase (7 files)
]

# 向后兼容
MIGRATIONS_DIR = MIGRATIONS_DIRS[0]

# 是否启用自动迁移
AUTO_MIGRATE = os.environ.get("AUTO_MIGRATE", "false").lower() in ("true", "1", "yes")

# 迁移文件名正则 (匹配 YYYYMMDD 开头的 .sql 文件)
MIGRATION_PATTERN = re.compile(r"^(\d{8}.*?)\.sql$")


async def _ensure_migration_table() -> bool:
    """
    确保 migration_history 表存在。
    返回 True 表示成功，False 表示无法创建。
    """
    from app.core.database import supabase

    if not supabase:
        return False

    try:
        # 尝试创建表（如果不存在）
        await supabase.rpc(
            "exec_sql",
            {
                "query": """
                CREATE TABLE IF NOT EXISTS public.migration_history (
                    id SERIAL PRIMARY KEY,
                    migration_name TEXT NOT NULL UNIQUE,
                    applied_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    checksum TEXT
                );
                """
            },
        ).execute()
        return True
    except Exception:
        # RPC 可能不存在，尝试通过查询表来检测是否已存在
        try:
            await supabase.table("migration_history").select("id").limit(1).execute()
            return True
        except Exception as e:
            logger.warning(f"[MigrationRunner] 无法创建或访问 migration_history 表: {e}")
            return False


async def _get_applied_migrations() -> set[str]:
    """获取已应用的迁移名称集合。"""
    from app.core.database import supabase

    if not supabase:
        return set()

    try:
        res = await supabase.table("migration_history").select("migration_name").execute()
        return {row["migration_name"] for row in (res.data or [])}
    except Exception as e:
        logger.warning(f"[MigrationRunner] 无法读取已应用迁移记录: {e}")
        return set()


async def _record_migration(migration_name: str, checksum: str = "") -> None:
    """记录已应用的迁移。"""
    from app.core.database import supabase

    if not supabase:
        return

    try:
        await (
            supabase.table("migration_history")
            .insert(
                {
                    "migration_name": migration_name,
                    "checksum": checksum,
                }
            )
            .execute()
        )
    except Exception as e:
        logger.warning(f"[MigrationRunner] 无法记录迁移 '{migration_name}': {e}")


def _get_pending_migrations(applied: set[str]) -> list[tuple[str, Path]]:
    """
    扫描所有迁移目录，返回未应用的迁移文件列表。
    按文件名排序以确保执行顺序。(Item 9/23: 统一扫描3个目录)
    """
    pending = []
    seen_names: set[str] = set()

    for migrations_dir in MIGRATIONS_DIRS:
        if not migrations_dir.exists():
            continue
        for f in sorted(migrations_dir.iterdir()):
            if f.is_file() and f.suffix == ".sql" and f.name not in applied and f.name not in seen_names:
                pending.append((f.name, f))
                seen_names.add(f.name)

    if not seen_names and not pending:
        logger.warning(f"[MigrationRunner] 所有迁移目录均不存在或为空: {MIGRATIONS_DIRS}")

    # 全局按文件名排序
    pending.sort(key=lambda x: x[0])
    return pending


async def run_migrations() -> list[str]:
    """
    执行自动迁移。

    返回已应用的迁移名称列表。
    如果 AUTO_MIGRATE 未启用，返回空列表。
    """
    from app.core.database import supabase

    # 动态检查环境变量 (Item 18)
    auto_migrate = os.environ.get("AUTO_MIGRATE", "false").lower() in ("true", "1", "yes")

    if not auto_migrate:
        logger.info("[MigrationRunner] 自动迁移未启用 (设置 AUTO_MIGRATE=true 启用)")
        return []

    logger.info("[MigrationRunner] 开始检查数据库迁移...")

    # 确保 migration_history 表存在
    table_ready = await _ensure_migration_table()
    if not table_ready:
        logger.warning("[MigrationRunner] 无法准备迁移表，跳过自动迁移")
        return []

    # 获取已应用的迁移
    applied = await _get_applied_migrations()
    logger.info(f"[MigrationRunner] 已应用 {len(applied)} 个迁移")

    # 获取待执行的迁移
    pending = _get_pending_migrations(applied)
    if not pending:
        logger.info("[MigrationRunner] 没有待执行的迁移")
        return []

    logger.info(f"[MigrationRunner] 发现 {len(pending)} 个待执行的迁移")

    # 注意: 自动执行 SQL 迁移需要数据库的 exec_sql RPC
    # 在大多数 Supabase 环境中，应使用 supabase db push 而不是自动执行
    # 这里仅记录待执行迁移，实际执行需要 DBA 确认
    applied_names = []
    for name, path in pending:
        logger.info(f"[MigrationRunner] 执行待决迁移: {name}")
        try:
            sql = path.read_text(encoding="utf-8")
            # 自动执行 SQL 迁移 需要数据库的 exec_sql RPC
            await supabase.rpc("exec_sql", {"query": sql}).execute()
            await _record_migration(name)
            applied_names.append(name)
            logger.info(f"[MigrationRunner] 成功执行迁移: {name}")
        except Exception as e:
            logger.error(f"[MigrationRunner] 迁移执行失败 '{name}': {e}")
            break  # 遇到错误停止执行

    return applied_names
