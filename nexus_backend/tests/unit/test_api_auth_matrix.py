"""Guardrails for unauthenticated `/api` routes."""

from app.core.api_auth_matrix import PUBLIC_API_ROUTE_REASONS
from app.core.route_introspection import iter_api_routes
from app.main import app


def _route_keys_without_dependencies() -> set[tuple[str, str]]:
    routes: set[tuple[str, str]] = set()
    for route in iter_api_routes(app.routes):
        if not route.path.startswith("/api"):
            continue
        if route.dependant.dependencies:
            continue
        for method in route.methods or set():
            if method in {"HEAD", "OPTIONS"}:
                continue
            routes.add((method, route.path))
    return routes


def test_every_dependency_free_api_route_is_explicitly_allowlisted():
    public_routes = _route_keys_without_dependencies()
    allowlisted = set(PUBLIC_API_ROUTE_REASONS)

    assert public_routes <= allowlisted


def test_public_api_route_allowlist_has_no_stale_entries():
    public_routes = _route_keys_without_dependencies()

    assert set(PUBLIC_API_ROUTE_REASONS) <= public_routes
