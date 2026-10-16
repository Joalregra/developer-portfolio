import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import Settings


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/health")

    body = response.json()
    assert response.status_code == 200
    assert (body["status"], body["environment"]) == ("ok", "test")
    assert len(body["knowledge_version"]) == 12


def test_cors_allows_the_frontend_origin(client: TestClient, settings: Settings) -> None:
    origin = settings.cors_origins[0]

    response = client.options(
        "/health", headers={"Origin": origin, "Access-Control-Request-Method": "GET"}
    )

    assert response.headers["access-control-allow-origin"] == origin


def test_cors_rejects_an_unknown_origin(client: TestClient) -> None:
    response = client.options(
        "/health",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"},
    )

    assert "access-control-allow-origin" not in response.headers


def test_knowledge_files_exist(settings: Settings) -> None:
    assert (settings.knowledge_dir / "ChatbotKnowledge.en.md").is_file()
    assert (settings.knowledge_dir / "ChatbotKnowledge.es.md").is_file()


@pytest.mark.parametrize(
    "origins",
    [
        pytest.param(["*"], id="wildcard"),
        pytest.param(["http://localhost:5173"], id="localhost"),
        pytest.param(["http://example.com"], id="not-https"),
        pytest.param(["https://example.com", "http://example.com"], id="one-bad-origin"),
        pytest.param([], id="empty"),
    ],
)
def test_production_refuses_unsafe_cors_origins(origins: list[str]) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, environment="production", cors_origins=origins)


def test_production_accepts_explicit_https_origins() -> None:
    settings = Settings(
        _env_file=None, environment="production", cors_origins=["https://portfolio.example"]
    )

    assert settings.is_production
