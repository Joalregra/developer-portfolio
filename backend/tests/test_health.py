import tomllib
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import Settings
from app.main import create_app


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


def test_the_api_version_matches_pyproject(app: FastAPI) -> None:
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    declared = tomllib.loads(pyproject.read_text(encoding="utf-8"))["project"]["version"]

    assert app.version == declared


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


@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json"])
def test_the_api_docs_are_closed_in_production_and_open_elsewhere(path: str) -> None:
    development = Settings(_env_file=None, environment="development", chat_enabled=False)
    production = Settings(
        _env_file=None,
        environment="production",
        chat_enabled=False,
        cors_origins=["https://yourdomain.com"],
    )

    assert TestClient(create_app(development)).get(path).status_code == 200
    assert TestClient(create_app(production)).get(path).status_code == 404
    # The health check is the one route production keeps public besides the chat endpoints.
    assert TestClient(create_app(production)).get("/health").status_code == 200
