"""FastAPI dependencies. Routes receive everything through these, which keeps them testable.

Nothing here creates resources: the app factory and the lifespan do, and store them on
`app.state`. Tests build an app with their own settings instead of patching globals.
"""

from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.services.chat_service import ChatService
from app.services.knowledge import Knowledge
from app.services.rate_limit import client_key

UNKNOWN_CLIENT = "unknown"


def get_app_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


SettingsDep = Annotated[Settings, Depends(get_app_settings)]


def get_session_factory(request: Request) -> async_sessionmaker[AsyncSession] | None:
    """Return the session factory, or None when no database is configured."""
    factory: async_sessionmaker[AsyncSession] | None = request.app.state.session_factory
    return factory


def get_knowledge(request: Request) -> Knowledge:
    knowledge: Knowledge = request.app.state.knowledge
    return knowledge


def get_chat_service(request: Request) -> ChatService | None:
    """Return the chat service, or None when the chat is switched off."""
    service: ChatService | None = request.app.state.chat_service
    return service


def get_client_key(request: Request) -> str:
    """Who is asking, for the rate limiter.

    Behind a proxy, uvicorn replaces `request.client` with the real address only if it was
    started with `--proxy-headers` and `FORWARDED_ALLOW_IPS` set to the proxy (SEC-03).
    """
    host = request.client.host if request.client else UNKNOWN_CLIENT
    return client_key(host)


def get_country(request: Request, settings: SettingsDep) -> str | None:
    """Country code of the visitor, only when Cloudflare is trusted to have set it."""
    if not settings.trust_cloudflare_headers:
        return None
    code = request.headers.get("cf-ipcountry", "").strip().upper()
    # "XX" and "T1" are Cloudflare's markers for an unknown country and for Tor.
    return code if len(code) == 2 and code.isalpha() and code != "XX" else None


SessionFactoryDep = Annotated[async_sessionmaker[AsyncSession] | None, Depends(get_session_factory)]
KnowledgeDep = Annotated[Knowledge, Depends(get_knowledge)]
ChatServiceDep = Annotated[ChatService | None, Depends(get_chat_service)]
ClientKeyDep = Annotated[str, Depends(get_client_key)]
CountryDep = Annotated[str | None, Depends(get_country)]
