from fastapi.testclient import TestClient

from app.core.config import get_settings


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "environment": "development"}


def test_cors_allows_the_frontend_origin(client: TestClient) -> None:
    origin = get_settings().cors_origins[0]
    response = client.options(
        "/health", headers={"Origin": origin, "Access-Control-Request-Method": "GET"}
    )

    assert response.headers["access-control-allow-origin"] == origin


def test_knowledge_file_exists() -> None:
    assert get_settings().knowledge_path.is_file()
