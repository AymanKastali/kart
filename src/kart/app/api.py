"""The `api` process: every HTTP route, served by uvicorn."""

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import FastAPI

from kart.app.settings import Settings

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    # Read the settings at startup, so a missing variable stops the process instead of
    # leaving a healthy-looking api that fails on its first real request.
    app.state.settings = Settings()
    yield


app = FastAPI(title="Kart", lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
