"""
LangGraph Checkpointer Factory — supports memory and postgres backends.

Memory checkpointer: Fast, but state is lost on restart. Good for development.
Postgres checkpointer: Persistent, supports state recovery and HITL async.

Usage:
    from app.agent.checkpointer import get_checkpointer
    checkpointer = get_checkpointer()
"""

import logging
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

# Singleton checkpointer instance
_checkpointer_instance = None


def get_checkpointer():
    """
    Factory function to create or return the singleton checkpointer.
    
    Backend is determined by LANGGRAPH_CHECKPOINTER setting:
    - "memory": In-memory checkpointer (default, dev mode)
    - "postgres": PostgreSQL-backed checkpointer (production)
    
    Returns:
        LangGraph checkpointer instance
    """
    global _checkpointer_instance
    
    if _checkpointer_instance is not None:
        return _checkpointer_instance
    
    backend = settings.LANGGRAPH_CHECKPOINTER.lower()
    
    if backend == "postgres":
        _checkpointer_instance = _create_postgres_checkpointer()
    else:
        _checkpointer_instance = _create_memory_checkpointer()
    
    return _checkpointer_instance


def _create_memory_checkpointer():
    """Create an in-memory checkpointer."""
    from langgraph.checkpoint.memory import MemorySaver
    
    logger.info("[Checkpointer] Using MemorySaver (non-persistent)")
    return MemorySaver()


def _create_postgres_checkpointer():
    """
    Create a PostgreSQL-backed checkpointer.
    
    Uses Supabase connection pool for reliability.
    Requires langgraph-checkpoint-postgres package.
    """
    try:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
        from psycopg_pool import AsyncConnectionPool
        
        # Build connection string from Supabase settings
        db_url = _build_postgres_url()
        
        # Create connection pool
        pool = AsyncConnectionPool(
            conninfo=db_url,
            max_size=10,
            min_size=2,
            open=False,  # Will be opened on first use
        )
        
        checkpointer = AsyncPostgresSaver(pool)
        
        logger.info("[Checkpointer] Using PostgreSQL checkpointer (persistent)")
        return checkpointer
        
    except ImportError as e:
        logger.warning(
            f"[Checkpointer] langgraph-checkpoint-postgres not installed, "
            f"falling back to memory: {e}"
        )
        return _create_memory_checkpointer()
    except Exception as e:
        logger.error(f"[Checkpointer] Failed to create PostgreSQL checkpointer: {e}")
        logger.warning("[Checkpointer] Falling back to memory checkpointer")
        return _create_memory_checkpointer()


def _build_postgres_url() -> str:
    """
    Build PostgreSQL connection URL from Supabase settings.
    
    Supabase provides:
    - SUPABASE_URL: https://xxxx.supabase.co
    - SUPABASE_SERVICE_KEY: service role key
    
    For direct Postgres connection, we need to transform:
    - Host: db.xxxx.supabase.co (Supabase pooler)
    - Port: 6543 (pooler) or 5432 (direct)
    - Database: postgres
    - User: postgres
    - Password: from service key or separate setting
    """
    supabase_url = settings.SUPABASE_URL
    
    if not supabase_url:
        raise ValueError("SUPABASE_URL is required for PostgreSQL checkpointer")
    
    # Extract project ref from Supabase URL
    # https://xxxx.supabase.co -> xxxx
    project_ref = supabase_url.replace("https://", "").split(".")[0]
    
    # Use connection pooler for serverless/production
    # Direct connection: db.xxxx.supabase.co:5432
    # Pooler: aws-0-ap-southeast-1.pooler.supabase.com:6543
    # For simplicity, use direct connection
    db_host = f"db.{project_ref}.supabase.co"
    db_port = 5432
    db_name = "postgres"
    db_user = "postgres"
    
    # Prefer dedicated database password if available
    # Otherwise, use the service key (which works as postgres password in Supabase)
    db_password = getattr(settings, "SUPABASE_DB_PASSWORD", None) or settings.SUPABASE_SERVICE_KEY
    
    if not db_password:
        raise ValueError("Database password required for PostgreSQL checkpointer")
    
    # Build URL with asyncpg driver
    url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    
    return url


async def setup_checkpointer():
    """
    Initialize the checkpointer (create tables, etc.).
    Call this at application startup.
    """
    checkpointer = get_checkpointer()
    
    # Postgres checkpointer needs setup
    if hasattr(checkpointer, "setup"):
        try:
            await checkpointer.setup()
            logger.info("[Checkpointer] PostgreSQL tables created/verified")
        except Exception as e:
            logger.error(f"[Checkpointer] Setup failed: {e}")
            raise
    
    return checkpointer


def reset_checkpointer():
    """
    Reset the singleton checkpointer instance.
    Used for testing or hot-reload scenarios.
    """
    global _checkpointer_instance
    _checkpointer_instance = None
    logger.info("[Checkpointer] Instance reset")