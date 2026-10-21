"""Rejects request bodies bigger than a configured size (SEC-04).

Pydantic limits the length of each field, but only after the whole body was read. This
middleware stops the read early. It does not validate content.
"""

from starlette.exceptions import HTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.errors import error_response

_TOO_LARGE_MESSAGE = "The request body is too large."


class BodySizeLimitMiddleware:
    """Pure ASGI middleware. Checks `Content-Length` first, then counts the bytes it reads."""

    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        declared = dict(scope["headers"]).get(b"content-length", b"")
        if declared.isdigit() and int(declared) > self.max_bytes:
            response = error_response(413, "payload_too_large", _TOO_LARGE_MESSAGE)
            await response(scope, receive, send)
            return

        received = 0

        async def counting_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                # Chunked uploads have no Content-Length, so the real size is only known now.
                # An HTTPException is used because FastAPI re-raises it as is, and the shared
                # handler then gives it the standard error shape.
                if received > self.max_bytes:
                    raise HTTPException(status_code=413, detail=_TOO_LARGE_MESSAGE)
            return message

        await self.app(scope, counting_receive, send)
