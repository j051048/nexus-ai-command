"""
Standalone migration runner for CI/CD pipelines.

Usage:
    cd nexus_backend
    python -m scripts.run_migrations

Environment:
    Requires the same environment variables as the main app:
    - SUPABASE_URL
    - SUPABASE_SERVICE_KEY
    - AUTO_MIGRATE=true  (forced automatically by this script)

Exit codes:
    0 — Success (migrations applied or none pending)
    1 — Failure (migration error or configuration issue)
"""

import asyncio
import logging
import os
import sys

# Ensure the nexus_backend package root is on sys.path
_script_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_script_dir)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("migration_runner")


async def main() -> int:
    """
    Run database migrations and return exit code.

    Returns:
        0 on success, 1 on failure.
    """
    logger.info("=== Nexus AI Command — Standalone Migration Runner ===")

    # Force AUTO_MIGRATE=true for standalone execution
    os.environ["AUTO_MIGRATE"] = "true"

    try:
        # Validate that essential environment variables are present
        supabase_url = os.environ.get("SUPABASE_URL")
        supabase_key = os.environ.get("SUPABASE_SERVICE_KEY")

        if not supabase_url or not supabase_key:
            logger.error(
                "Missing required environment variables: "
                "SUPABASE_URL and SUPABASE_SERVICE_KEY must be set."
            )
            return 1

        logger.info(f"Supabase URL: {supabase_url[:40]}...")

        # Step 1: Run schema validation (read-only, safe)
        logger.info("--- Step 1: Schema Validation ---")
        try:
            from app.core.schema_validator import validate_schema

            warnings = await validate_schema()
            if warnings:
                logger.warning(f"Schema validation: {len(warnings)} warnings")
                for w in warnings:
                    logger.warning(f"  - {w}")
            else:
                logger.info("Schema validation passed (no warnings)")
        except Exception as e:
            logger.warning(f"Schema validation skipped: {e}")

        # Step 2: Run migrations
        logger.info("--- Step 2: Database Migrations ---")
        from app.core.migration_runner import run_migrations

        applied = await run_migrations()

        if applied:
            logger.info(f"Successfully processed {len(applied)} migration(s):")
            for name in applied:
                logger.info(f"  - {name}")
        else:
            logger.info("No pending migrations to apply.")

        logger.info("=== Migration runner completed successfully ===")
        return 0

    except Exception as e:
        logger.error(f"Migration runner failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
