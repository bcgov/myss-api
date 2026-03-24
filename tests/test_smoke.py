# tests/test_smoke.py
import pytest
from httpx import AsyncClient


def test_import_app():
    from app.main import app
    assert app is not None


@pytest.mark.asyncio
async def test_app_returns_response(client: AsyncClient):
    """Verify the ASGI app handles HTTP requests end-to-end."""
    response = await client.get("/health")
    # /health may not exist yet — we just verify we get a response, not a 500
    assert response.status_code != 500
