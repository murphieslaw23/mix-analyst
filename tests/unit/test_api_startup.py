"""Startup regression test for the HTTP API."""

import os


def test_application_imports_and_registers_health_routes():
    """A deployment must be able to import the ASGI application."""
    os.environ["DATABASE_URL"] = "postgresql+psycopg2://mixuser:mixpassword@postgres:5432/mixanalyst"
    os.environ["STORAGE_ROOT"] = "/tmp/mix-analyst-test-storage"
    os.environ["ALLOWED_ORIGINS"] = '["http://localhost"]'

    from api.app.main import app

    paths = {
        f"{route.include_context.prefix}{child.path}"
        for route in app.routes
        if hasattr(route, "include_context")
        for child in route.original_router.routes
    }
    assert "/api/v1/health/live" in paths
    assert "/api/v1/health/ready" in paths
