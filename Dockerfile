# One image for every Kart process: compose picks the command (api, worker, scheduler,
# migrate or rabbitmq-setup).
FROM python:3.14-slim

COPY --from=ghcr.io/astral-sh/uv:0.13 /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_DEV=1 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Dependencies first, so code changes don't reinstall them.
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project

COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-editable

RUN useradd --system --no-create-home kart
USER kart

CMD ["uvicorn", "kart.app.api:app", "--host", "0.0.0.0", "--port", "8000"]
