"""The `api` process: every HTTP route, served by uvicorn: `python -m kart.app.api`."""

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

import uvicorn
from fastapi import Depends, FastAPI

from kart.app.audiences import admit_only_the_audience
from kart.app.database import create_database_engine, units_of_work
from kart.app.observability import set_up_observability
from kart.app.settings import Settings
from kart.contexts.identity.api import routes as identity_routes
from kart.contexts.identity.application.seller_sign_up import SellerSignUp
from kart.contexts.identity.infrastructure.account_repository import PostgresAccountRepository
from kart.contexts.identity.infrastructure.keycloak_access_tokens import keycloak_access_tokens
from kart.contexts.identity.infrastructure.keycloak_identity_provider import (
    KeycloakIdentityProvider,
)
from kart.contexts.seller_onboarding.api import routes as seller_onboarding_routes
from kart.contexts.seller_onboarding.application.seller_applications import SellerApplications
from kart.contexts.seller_onboarding.infrastructure.seller_application_repository import (
    PostgresSellerApplicationRepository,
)

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, MutableMapping

_HEALTH_PATH = "/health"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    # Read the settings at startup, so a missing variable stops the process instead of
    # leaving a healthy-looking api that fails on its first real request.
    settings = Settings()
    engine = create_database_engine(settings.database_url)
    # The one place the use cases are handed the adapters that implement their ports.
    app.state.access_tokens = keycloak_access_tokens(settings.keycloak_url)
    app.state.seller_sign_up = SellerSignUp(
        KeycloakIdentityProvider(settings.keycloak_admin),
        units_of_work(engine, "identity", PostgresAccountRepository),
    )
    app.state.seller_applications = SellerApplications(
        units_of_work(engine, "seller_onboarding", PostgresSellerApplicationRepository)
    )
    yield
    engine.dispose()


def create_app() -> FastAPI:
    # Every route checks its audience's role, so a route can't be left open by mistake.
    app = FastAPI(
        title="Kart",
        lifespan=lifespan,
        dependencies=[Depends(admit_only_the_audience)],
        # FastAPI traces each request itself.
        telemetry={"exclude": _is_health_check},
    )
    app.get(_HEALTH_PATH)(health)
    app.include_router(identity_routes.router)
    app.include_router(seller_onboarding_routes.router)
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
