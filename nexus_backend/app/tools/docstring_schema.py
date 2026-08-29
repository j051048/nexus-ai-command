"""
Docstring to JSON Schema — 自动从 FastAPI 路由端点生成 Tool 定义。

扫描指定 router 模块中的端点函数，提取：
1. 函数 docstring → tool description
2. Pydantic Body model → JSON Schema parameters
3. 路由路径 + HTTP method → tool name

用法::

    from app.tools.docstring_schema import generate_tool_schemas_from_router
    schemas = generate_tool_schemas_from_router("app.routers.attendance")
"""

import importlib
import inspect
import logging
import re
from typing import Any

from pydantic import BaseModel

logger = logging.getLogger(__name__)

# HTTP method → action prefix mapping
_METHOD_PREFIX = {
    "GET": "query",
    "POST": "create",
    "PUT": "update",
    "PATCH": "update",
    "DELETE": "delete",
}


def _path_to_tool_name(path: str, method: str) -> str:
    """Convert route path + method to a snake_case tool name.

    Example: POST /api/attendance/clock → create_attendance_clock
    """
    # Strip /api/ prefix and path params
    clean = re.sub(r"/api/", "", path)
    clean = re.sub(r"\{[^}]+\}", "", clean)
    clean = clean.strip("/").replace("/", "_").replace("-", "_")
    clean = re.sub(r"_+", "_", clean).strip("_")
    prefix = _METHOD_PREFIX.get(method.upper(), method.lower())
    return f"{prefix}_{clean}" if clean else prefix


def _pydantic_to_json_schema(model: type[BaseModel]) -> dict[str, Any]:
    """Extract JSON Schema from a Pydantic model class."""
    try:
        schema = model.model_json_schema()
        # Flatten $defs if present (Pydantic v2)
        schema.pop("$defs", None)
        schema.pop("definitions", None)
        return schema
    except Exception:
        return {"type": "object", "properties": {}}


def _extract_body_model(func) -> type[BaseModel] | None:
    """Extract the Pydantic Body model from a FastAPI endpoint's signature."""
    sig = inspect.signature(func)
    for param in sig.parameters.values():
        ann = param.annotation
        if ann is inspect.Parameter.empty:
            continue
        if isinstance(ann, type) and issubclass(ann, BaseModel):
            return ann
    return None


def _extract_query_params(func) -> dict[str, Any]:
    """Extract query parameters (non-Pydantic, non-Request, non-Depends) from signature."""
    sig = inspect.signature(func)
    properties: dict[str, Any] = {}
    required: list[str] = []

    skip_types = {"Request", "str"}  # str is typically user_id from Depends

    for name, param in sig.parameters.items():
        ann = param.annotation
        if ann is inspect.Parameter.empty:
            continue
        if isinstance(ann, type) and issubclass(ann, BaseModel):
            continue
        # Skip Request, Depends-injected params
        ann_name = getattr(ann, "__name__", str(ann))
        if ann_name in skip_types or name in ("request", "req", "user_id", "db"):
            continue

        # Map Python types to JSON Schema types
        type_map = {int: "integer", float: "number", str: "string", bool: "boolean"}
        json_type = type_map.get(ann, "string") if isinstance(ann, type) else "string"

        prop: dict[str, Any] = {"type": json_type}
        if param.default is not inspect.Parameter.empty and param.default is not None:
            prop["default"] = param.default
        else:
            required.append(name)

        properties[name] = prop

    if not properties:
        return {}

    schema: dict[str, Any] = {"type": "object", "properties": properties}
    if required:
        schema["required"] = required
    return schema


def generate_tool_schema_from_endpoint(
    func,
    path: str,
    method: str,
) -> dict[str, Any] | None:
    """Generate a single tool schema dict from a FastAPI endpoint function.

    Returns:
        {"name": ..., "description": ..., "parameters": {...}} or None
    """
    docstring = inspect.getdoc(func) or ""
    if not docstring:
        return None

    tool_name = _path_to_tool_name(path, method)

    # Try Pydantic body model first, then query params
    body_model = _extract_body_model(func)
    if body_model:
        parameters = _pydantic_to_json_schema(body_model)
    else:
        parameters = _extract_query_params(func)

    if not parameters:
        parameters = {"type": "object", "properties": {}}

    return {
        "name": tool_name,
        "description": docstring.strip(),
        "parameters": parameters,
        "source": f"{method.upper()} {path}",
    }


def generate_tool_schemas_from_router(
    router_module_path: str,
) -> list[dict[str, Any]]:
    """Scan a FastAPI router module and generate tool schemas from all endpoints.

    Args:
        router_module_path: Dotted module path, e.g. "app.routers.attendance"

    Returns:
        List of tool schema dicts
    """
    try:
        module = importlib.import_module(router_module_path)
    except ImportError:
        logger.warning(f"[DocstringSchema] Cannot import {router_module_path}")
        return []

    router = getattr(module, "router", None)
    if router is None:
        logger.warning(f"[DocstringSchema] No 'router' found in {router_module_path}")
        return []

    schemas: list[dict[str, Any]] = []

    from app.core.route_introspection import iter_effective_routes

    for route in iter_effective_routes(router.routes):
        if not hasattr(route, "endpoint"):
            continue
        func = route.endpoint
        path = getattr(route, "path", "")
        methods = getattr(route, "methods", {"GET"})
        method = next(iter(methods)) if methods else "GET"

        schema = generate_tool_schema_from_endpoint(func, path, method)
        if schema:
            schemas.append(schema)

    logger.info(
        f"[DocstringSchema] Generated {len(schemas)} tool schemas from {router_module_path}"
    )
    return schemas


def generate_all_router_schemas(
    router_modules: list[str] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Batch generate tool schemas from multiple router modules.

    Args:
        router_modules: List of module paths. If None, scans app.routers package.

    Returns:
        {module_path: [schema, ...]}
    """
    if router_modules is None:
        # Auto-discover routers
        try:
            import pkgutil

            package = importlib.import_module("app.routers")
            pkg_paths = getattr(package, "__path__", [])
            router_modules = []
            for _importer, modname, ispkg in pkgutil.iter_modules(
                pkg_paths, "app.routers."
            ):
                if not ispkg and not modname.endswith("__init__"):
                    router_modules.append(modname)
        except Exception as e:
            logger.warning(f"[DocstringSchema] Auto-discover failed: {e}")
            return {}

    results: dict[str, list[dict[str, Any]]] = {}
    for mod_path in router_modules:
        try:
            schemas = generate_tool_schemas_from_router(mod_path)
            if schemas:
                results[mod_path] = schemas
        except Exception as e:
            logger.debug(f"[DocstringSchema] Skipped {mod_path}: {e}")

    total = sum(len(v) for v in results.values())
    logger.info(f"[DocstringSchema] Total: {total} schemas from {len(results)} routers")
    return results
