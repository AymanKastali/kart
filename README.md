# Kart

A learning and portfolio clone of the noon.com UAE marketplace, built as a modular monolith with strict bounded-context boundaries. Domain terms are in [`GLOSSARY.md`](GLOSSARY.md); the design is in [`docs/architecture/`](docs/architecture/) and the decisions in [`docs/adr/`](docs/adr/).

## Setup

Install [uv](https://docs.astral.sh/uv/), then from the repository root:

```sh
uv sync
```

uv installs Python 3.14 if needed, creates `.venv` and installs `kart` from `src/` in editable mode. Run everything through `uv run`.

## Run locally

The local stack runs in Docker Compose. So far it has Postgres (with `wal_level=logical`), RabbitMQ, Keycloak, and Kart's `api`, `worker` and `scheduler` processes, all from one image. Debezium Server, MinIO and Mailpit join as later tickets need them. You need Docker with Compose v2.

```sh
cp .env.example .env    # once; .env is not committed
docker compose -f deploy/compose.yaml up --build --wait
```

`--wait` returns once the infrastructure and the `api` pass their healthchecks and the `worker` and `scheduler` are running. Then, with the users and passwords from `.env`:

| Service | URL |
|---|---|
| API health | http://localhost:8000/health |
| API docs (OpenAPI) | http://localhost:8000/docs |
| RabbitMQ management | http://localhost:15672 |
| Keycloak admin | http://localhost:8080 |
| Postgres | `localhost:5432` |

Ports listen on localhost only. Stop the stack with `docker compose -f deploy/compose.yaml down`. Add `-v` to also delete the Postgres and RabbitMQ data.

### Configuration

`.env` is the one place the local users, passwords and hosts are set:

- Postgres, RabbitMQ and Keycloak create their users from it.
- Every Kart process reads it at startup through `kart.app.settings`, which builds the database and RabbitMQ URLs from it. A process refuses to start if a value is missing.
- Inside Compose, the hosts are replaced with the service names (`postgres`, `rabbitmq`, `keycloak`).

To run a process on your machine against the Compose infrastructure, for example `uv run uvicorn kart.app.api:app --reload --port 8001`, run it from the repository root so it finds `.env`. Real environment variables override `.env`.

## Checks

CI runs these on every pull request and on pushes to `main`:

| Check | Command |
|---|---|
| Formatting | `uv run ruff format --check .` (fix with `uv run ruff format .`) |
| Lint | `uv run ruff check .` |
| Types | `uv run ty check` |
| Context boundaries | `uv run lint-imports` |
| Tests | `uv run pytest` |
| Image | `docker build .`, plus a check that `deploy/compose.yaml` is valid |

`lint-imports` enforces the boundaries described in [`overview.md`](docs/architecture/overview.md#inside-a-context): a context imports another context only through its `contracts`, a `contracts` module never exposes its context's internals, contexts never import `kart.app`, and both the shared kernel and the `domain` packages of Ordering, Fulfilment and Offer stay free of FastAPI (and Starlette), SQLAlchemy and Pydantic. `tests/shared_kernel/` also runs `ty` on a sample module to prove that passing one kind of id where another is expected fails type checking. The contracts live in `pyproject.toml`, and `tests/architecture/` proves each one catches what it should.
