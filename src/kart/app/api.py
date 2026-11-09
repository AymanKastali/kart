"""The `api` process: every HTTP route, served by uvicorn: `python -m kart.app.api`."""

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

import uvicorn
from fastapi import Depends, FastAPI

from kart.app.audiences import principal_for_audience
from kart.app.observability import set_up_observability
from kart.app.settings import Settings
from kart.contexts.identity.contracts import AccessTokens

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, MutableMapping

_HEALTH_PATH = "/health"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    # Read the settings at startup, so a missing variable stops the process instead of
    # leaving a healthy-looking api that fails on its first real request.
    settings = Settings()
    app.state.access_tokens = AccessTokens(settings.keycloak_url)
    yield


def create_app() -> FastAPI:
    # Every route checks its audience's role, so a route can't be left open by mistake.
    app = FastAPI(
        title="Kart",
        lifespan=lifespan,
        dependencies=[Depends(principal_for_audience)],
        # FastAPI traces each request itself.
        telemetry={"exclude": _is_health_check},
    )
    app.get(_HEALTH_PATH)(health)
    return app


def _is_health_check(scope: MutableMapping[str, Any]) -> bool:
    # Compose asks every few seconds, which would bury the traces worth reading.
    return scope["path"] == _HEALTH_PATH


def health() -> dict[str, str]:
    return {"status": "ok"}


app = create_app()

if __name__ == "__main__":
    set_up_observability("api", Settings())
    # No log config of its own, so uvicorn's loggers write JSON lines too.
    uvicorn.run(app, host="0.0.0.0", port=8000, log_config=None)  # noqa: S104 inside its container
