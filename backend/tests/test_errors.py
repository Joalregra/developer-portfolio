import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field

from app.core.errors import AssistantUnavailableError, RateLimitedError
from app.core.locale import Locale


class _Payload(BaseModel):
    message: str = Field(min_length=1, max_length=10)


@pytest.fixture
def failing_app(app: FastAPI) -> FastAPI:
    """The real app plus routes that fail in the ways the handlers must cover."""

    @app.get("/test/crash")
    async def crash() -> None:
        raise RuntimeError("secret database password")

    @app.get("/test/rate-limited")
    async def rate_limited() -> None:
        raise RateLimitedError(retry_after_seconds=30)

    @app.get("/test/unavailable")
    async def unavailable(lang: Locale) -> None:
        raise AssistantUnavailableError(locale=lang)

    @app.post("/test/validate")
    async def validate(payload: _Payload) -> None:
        return None

    return app


@pytest.fixture
def failing_client(failing_app: FastAPI) -> TestClient:
    return TestClient(failing_app)


def test_unknown_route_uses_the_standard_error_shape(client: TestClient) -> None:
    response = client.get("/nope", headers={"X-Request-ID": "abc-123"})

    assert response.status_code == 404
    assert response.headers["X-Request-ID"] == "abc-123"
    assert response.json() == {
        "error": {
            "code": "not_found",
            "message": "Not Found",
            "request_id": "abc-123",
            "details": None,
        }
    }


def test_unsafe_request_id_is_replaced(client: TestClient) -> None:
    response = client.get("/health", headers={"X-Request-ID": "bad id\twith spaces"})

    request_id = response.headers["X-Request-ID"]
    assert request_id != "bad id\twith spaces"
    assert len(request_id) == 32


def test_validation_error_does_not_echo_the_input(failing_client: TestClient) -> None:
    response = failing_client.post("/test/validate", json={"message": "x" * 50})

    body = response.json()["error"]
    assert response.status_code == 422
    assert body["code"] == "invalid_request"
    assert "x" * 50 not in response.text


def test_unexpected_exception_returns_500_without_details(failing_client: TestClient) -> None:
    response = failing_client.get("/test/crash")

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "internal_error"
    assert "secret" not in response.text
    assert response.json()["error"]["request_id"] == response.headers["X-Request-ID"]


def test_rate_limited_error_sends_retry_after(failing_client: TestClient) -> None:
    response = failing_client.get("/test/rate-limited")

    assert response.status_code == 429
    assert response.headers["Retry-After"] == "30"
    assert response.json()["error"]["code"] == "rate_limited"


@pytest.mark.parametrize(
    ("lang", "expected"),
    [("es", "no está disponible"), ("en", "unavailable right now")],
)
def test_visitor_message_follows_the_locale(
    failing_client: TestClient, lang: str, expected: str
) -> None:
    response = failing_client.get("/test/unavailable", params={"lang": lang})

    assert response.status_code == 503
    assert expected in response.json()["error"]["message"]
