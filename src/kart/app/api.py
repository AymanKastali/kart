"""The `api` process: every HTTP route, served by uvicorn."""

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import Depends, FastAPI

from kart.app.audiences import principal_for_audience
from kart.app.settings import Settings
from kart.contexts.identity.keycloak import KeycloakAccessTokens

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    # Read the settings at startup, so a missing variable stops the process instead of
    # leaving a healthy-looking api that fails on its first real request.
    settings = Settings()
    app.state.access_tokens = KeycloakAccessTokens(settings.keycloak_url)
    yield


def create_app() -> FastAPI:
    # Every route checks its audience's role, so a route can't be left open by mistake.
    app = FastAPI(title="Kart", lifespan=lifespan, dependencies=[Depends(principal_for_audience)])
    app.get("/health")(health)
    return app


def health() -> dict[str, str]:
    return {"status": "ok"}


app = create_app()
