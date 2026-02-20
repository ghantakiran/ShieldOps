"""Helper for tenant middleware tests.

This module intentionally does NOT use ``from __future__ import annotations``
so that FastAPI can resolve the ``Request`` type hint at runtime.
"""

from typing import Any

from fastapi import FastAPI, Request


def make_tenant_test_app(middleware_cls: type) -> FastAPI:
    """Build a tiny app with the given middleware and a test endpoint."""
    app = FastAPI()
    app.add_middleware(middleware_cls)

    @app.get("/test-tenant")
    async def _endpoint(request: Request) -> dict[str, Any]:
        org_id = getattr(request.state, "organization_id", None)
        return {"org_id": org_id}

    return app
