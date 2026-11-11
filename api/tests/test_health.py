from httpx import ASGITransport, AsyncClient

from app.main import create_app


async def test_health_reports_status() -> None:
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["db"] in {"ok", "unavailable"}
