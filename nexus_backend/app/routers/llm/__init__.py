"""LLM sub-router package — assembles all sub-routers into one ``router``.

Usage in main.py stays unchanged::

    from app.routers import llm_models
    app.include_router(llm_models.router)
"""

from fastapi import APIRouter

from .marketplace import router as marketplace_router
from .models_crud import router as models_crud_router
from .policy import router as policy_router
from .scheduling import router as scheduling_router

router = APIRouter(prefix="/api/llm", tags=["LLM Models"])

# Include all sub-routers (no extra prefix — each sub-module defines
# paths relative to /api/llm, e.g. "/models", "/schedule-rules", etc.)
router.include_router(models_crud_router)
router.include_router(scheduling_router)
router.include_router(marketplace_router)
router.include_router(policy_router)
