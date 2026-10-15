from collections.abc import Iterator

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app

LIMIT = 100


@pytest.fixture
def small_limit_client() -> TestClient:
    settings = Settings(_env_file=None, environment="test", max_body_bytes=LIMIT)
    app: FastAPI = create_app(settings)

    @app.post("/test/echo-size")
    async def echo_size(request: Request) -> dict[str, int]:
        return {"size": len(await request.body())}

    return TestClient(app)


def test_body_within_the_limit_is_accepted(small_limit_client: TestClient) -> None:
    response = small_limit_client.post("/test/echo-size", content=b"x" * LIMIT)

    assert response.status_code == 200
    assert response.json() == {"size": LIMIT}


def test_declared_oversized_body_gets_413(small_limit_client: TestClient) -> None:
    response = small_limit_client.post("/test/echo-size", content=b"x" * (LIMIT + 1))

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "payload_too_large"
    assert "X-Request-ID" in response.headers


def test_chunked_oversized_body_gets_413(small_limit_client: TestClient) -> None:
    def chunks() -> Iterator[bytes]:
        # No Content-Length is sent, so only the byte count while reading can stop it.
        for _ in range(5):
            yield b"x" * 40

    response = small_limit_client.post("/test/echo-size", content=chunks())

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "payload_too_large"
