"""Application factory. Wires settings, middleware, error handlers and routers; no logic."""

import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import chat, health
from app.core.body_limit import BodySizeLimitMiddleware
from app.core.config import Settings, get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import RequestContextMiddleware, configure_logging
from app.db.session import create_engine, create_session_factory, warn_if_event_loop_unsupported
from app.services.chat_setup import ChatRuntime, build_chat_runtime
from app.services.feedback import FeedbackService
from app.services.knowledge import load_knowledge

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Create the database engine and the chat and feedback services once, and close them on
    shutdown.

    Without `DATABASE_URL` there is no engine: the chat still works, it just logs nothing.
    If the chat is switched on but a setting is missing, the app does not start.
    """
    settings: Settings = app.state.settings
    engine = None
    runtime: ChatRuntime | None = None
    if settings.database_url is not None:
        engine = create_engine(settings.database_url.get_secret_value())
        app.state.session_factory = create_session_factory(engine)
        warn_if_event_loop_unsupported()
    else:
        # A typo in the production environment would otherwise disable the log silently.
        logger.warning("database_not_configured")
    app.state.feedback_service = FeedbackService.with_default_limits(app.state.session_factory)
    if settings.is_production and "FORWARDED_ALLOW_IPS" not in os.environ:
        # Without it every visitor looks like the proxy and shares one rate limit (SEC-03).
        logger.warning("forwarded_allow_ips_not_set")
    if settings.chat_enabled:
        runtime = build_chat_runtime(settings, app.state.knowledge, app.state.session_factory)
        runtime.start()
        app.state.chat_service = runtime.service
    try:
        yield
    finally:
        if runtime is not None:
            await (
                runtime.aclose()
            )  # saves the state and the last log rows before the engine goes away
        if engine is not None:
            await engine.dispose()


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the app. Tests pass their own `settings`; production uses the cached ones."""
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    # The interactive docs and the schema describe every endpoint to anyone, so production turns
    # them off. Locally they stay at /docs.
    docs_enabled = not settings.is_production
    app = FastAPI(
        title=settings.app_name,
        version="1.1.0",
        lifespan=lifespan,
        docs_url="/docs" if docs_enabled else None,
        redoc_url="/redoc" if docs_enabled else None,
        openapi_url="/openapi.json" if docs_enabled else None,
    )
    app.state.settings = settings
    # Loaded here, not in the lifespan: a broken knowledge file stops the start at once, and
    # /health can report the version. Defaults below keep tests that skip the lifespan working.
    app.state.knowledge = load_knowledge(settings.knowledge_dir)
    app.state.session_factory = None
    app.state.chat_service = None
    app.state.feedback_service = None

    # Each call wraps the previous ones, so the last one added is the outermost layer.
    # Order, outside to inside: request context -> CORS -> body size limit. The outermost layer
    # sees every request and every error, and CORS headers also reach the 413 responses.
    app.add_middleware(BodySizeLimitMiddleware, max_bytes=settings.max_body_bytes)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
        expose_headers=["X-Request-ID"],
    )
    app.add_middleware(RequestContextMiddleware)

    register_exception_handlers(app)
    app.include_router(health.router)
    app.include_router(chat.router)
    return app


app = create_app()
