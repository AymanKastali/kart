"""The `api` process: every HTTP route, served by uvicorn."""

from fastapi import FastAPI

app = FastAPI(title="Kart")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
