"""LLM sub-router package — assembles all sub-routers into one ``router``.

Usage in main.py stays unchanged::

    from app.routers import llm_models
    app.include_router(llm_models.router)
"""

from fastapi import APIRouter

from .marketplace import router as marketplace_router
from .models_crud import router as models_crud_router
from .scheduling import router as scheduling_router

router = APIRouter(tags=["LLM Models"])

# Include sub-routers with explicit prefixes
# These will be accessible at /api/llm/models, /api/llm/available-models, etc.
router.include_router(models_crud_router, prefix="/api/llm")
router.include_router(scheduling_router, prefix="/api/llm")
router.include_router(marketplace_router, prefix="/api/llm")
