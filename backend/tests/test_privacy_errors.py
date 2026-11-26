from fastapi import Request
from fastapi.testclient import TestClient

from app.main import create_app


def test_unhandled_private_request_does_not_log_request_content(caplog):
    app = create_app()

    @app.post("/api/v1/journals/test-private-error")
    async def fail(request: Request):
        raise RuntimeError((await request.body()).decode())

    secret = "synthetic-private-error-marker"
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/journals/test-private-error",
            content=secret,
            headers={"Origin": "http://localhost:5173"},
        )

    assert response.status_code == 500
    assert response.json() == {"code": 50000, "message": "Internal server error", "data": None}
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert "Unhandled request error (RuntimeError)" in caplog.text
    assert secret not in caplog.text
    assert all(record.exc_info is None for record in caplog.records)
