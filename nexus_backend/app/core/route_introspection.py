"""Version-tolerant FastAPI route introspection helpers."""

from collections.abc import Iterable, Iterator
from typing import Any

from fastapi.routing import APIRoute


def iter_effective_routes(routes: Iterable[Any]) -> Iterator[Any]:
    """Yield concrete routes from eager and FastAPI lazy router containers."""
    for route in routes:
        effective_candidates = getattr(route, "effective_candidates", None)
        if callable(effective_candidates):
            yield from iter_effective_routes(effective_candidates())
        else:
            yield route


def iter_api_routes(routes: Iterable[Any]) -> Iterator[Any]:
    """Yield API route-like objects while preserving their effective metadata."""
    for route in iter_effective_routes(routes):
        original_route = getattr(route, "original_route", route)
        if isinstance(original_route, APIRoute):
            yield route
