# Kart

A learning and portfolio clone of the noon.com UAE marketplace, built as a modular monolith with strict bounded-context boundaries. Domain terms are in [`GLOSSARY.md`](GLOSSARY.md); the design is in [`docs/architecture/`](docs/architecture/) and the decisions in [`docs/adr/`](docs/adr/).

## Run it

Kart deploys as one Docker Compose stack. You need only Docker with Compose v2: there are no setup steps before, and nothing to run by hand after.

```sh
docker compose -f deploy/compose.yaml up --build --wait
```

This starts Postgres (with `wal_level=logical`), RabbitMQ, Keycloak, Debezium Server, and Kart's processes, all from one image. First `migrate` brings every context's schema up to date, prepares the outbox publication and replication slot, and exits, and `topology` declares the RabbitMQ exchange and every context's queues and exits; then `api`, `worker`, `scheduler` and `debezium` start. Both run on every `up` and change nothing when there is nothing new. MinIO and Mailpit join as later tickets need them. `--wait` returns once `migrate` and `topology` have succeeded, the infrastructure, `debezium` and the `api` pass their healthchecks, and the `worker` and `scheduler` are running. Then, with the users and passwords from `.env.example`:

| Service | URL |
|---|---|
| API health | http://localhost:8000/health |
| API docs (OpenAPI) | http://localhost:8000/docs |
| RabbitMQ management | http://localhost:15672 |
| Keycloak admin | http://localhost:8080 |
| Postgres | `localhost:5432` |

Ports listen on localhost only. Follow the logs with `docker compose -f deploy/compose.yaml logs -f`. Stop the stack with `docker compose -f deploy/compose.yaml down`, and add `-v` to also delete the Postgres, RabbitMQ and Debezium data.

### Configuration

`.env.example` is the one place the local users, passwords and hosts are set, and Compose hands it to every container as it is:

- Postgres, RabbitMQ and Keycloak create their users from it, and Debezium Server connects with them.
- Every Kart process reads it at startup through `kart.app.settings`, which builds the database and RabbitMQ URLs from it. A process refuses to start if a value is missing.

To change a value without editing `.env.example`, put it in a `.env` file at the repository root. Git ignores that file, and Compose reads it after `.env.example`.

## Development

The checks run on your machine through [uv](https://docs.astral.sh/uv/). Running the app doesn't need it. The tests in `tests/database/` and `tests/building_blocks/` start a throwaway Postgres, RabbitMQ and Debezium Server in Docker through testcontainers, so Docker must be running. Run `uv sync` once: uv installs Python 3.14 if needed, creates `.venv` and installs `kart` from `src/` in editable mode.

CI runs these on every pull request and on pushes to `main`:

| Check | Command |
|---|---|
| Formatting | `uv run ruff format --check .` (fix with `uv run ruff format .`) |
| Lint | `uv run ruff check .` |
| Types | `uv run ty check` |
| Context boundaries | `uv run lint-imports` |
| Tests | `uv run pytest` |
| Deployment | `docker compose -f deploy/compose.yaml up --build --wait` on an empty database, then a check that every context was migrated, the exchanges were declared and Debezium is reading the replication slot |

`lint-imports` enforces the boundaries described in [`overview.md`](docs/architecture/overview.md#inside-a-context): a context imports another context only through its `contracts`, a `contracts` module never exposes its context's internals, contexts never import `kart.app`, only a context's `infrastructure` and `migrations` use `kart.building_blocks`, and both the shared kernel and the `domain` packages of Ordering, Fulfilment and Offer stay free of FastAPI (and Starlette), SQLAlchemy and Pydantic. `tests/shared_kernel/` also runs `ty` on a sample module to prove that passing one kind of id where another is expected fails type checking. The contracts live in `pyproject.toml`, and `tests/architecture/` proves each one catches what it should.
