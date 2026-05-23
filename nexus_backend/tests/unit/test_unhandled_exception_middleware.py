import logging

import pytest
from httpx import ASGITransport, AsyncClient
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

from app.core.security_middleware import UnhandledExceptionMiddleware


async def _boom(_request):
    raise RuntimeError("database exploded")


async def _ok(_request):
    return JSONResponse({"ok": True})


@pytest.mark.asyncio
async def test_unhandled_exception_middleware_returns_safe_json(caplog):
    app = Starlette(routes=[Route("/boom", _boom)])
    app.add_middleware(UnhandledExceptionMiddleware)

    with caplog.at_level(logging.ERROR, logger="app.core.security_middleware"):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            resp = await client.get("/boom", headers={"X-Trace-ID": "trace-1"})

    assert resp.status_code == 500
    assert resp.json() == {
        "success": False,
        "error": {
            "code": "SYSTEM_INTERNAL_ERROR",
            "message": "系统内部错误，请稍后重试",
            "trace_id": "trace-1",
        },
    }
    assert "Unhandled request exception" in caplog.text
    assert "path=/boom" in caplog.text
    assert "trace_id=trace-1" in caplog.text


@pytest.mark.asyncio
async def test_unhandled_exception_middleware_passes_success_response():
    app = Starlette(routes=[Route("/ok", _ok)])
    app.add_middleware(UnhandledExceptionMiddleware)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.get("/ok")

    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
