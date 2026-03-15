"""Application startup modules: lifespan, middleware, routers."""

from app.startup.lifespan import lifespan
from app.startup.middleware import register_middleware
from app.startup.routers import register_routers

__all__ = ["lifespan", "register_middleware", "register_routers"]
