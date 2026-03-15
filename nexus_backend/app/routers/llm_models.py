"""LLM Model Management API - thin aggregator.

All endpoint logic has been split into sub-modules under ``app.routers.llm``.
This file re-exports ``router`` so that existing imports in main.py keep working::

    from app.routers import llm_models
    app.include_router(llm_models.router)
"""

from app.routers.llm import router  # noqa: F401

__all__ = ["router"]
