# Kart

A learning and portfolio clone of the noon.com UAE marketplace, built as a modular monolith with strict bounded-context boundaries. Domain terms are in [`GLOSSARY.md`](GLOSSARY.md); the design is in [`docs/architecture/`](docs/architecture/) and the decisions in [`docs/adr/`](docs/adr/).

## Run it

Kart deploys as one Docker Compose stack. You need only Docker with Compose v2: there are no setup steps before, and nothing to run by hand after.

```sh
docker compose up --build --wait
```

This starts Postgres (with `wal_level=logical`), RabbitMQ, Keycloak, Mailpit, Debezium Server, Jaeger, and Kart's processes, all from one image. First `migrate` brings every context's schema up to date, prepares the outbox publication and replication slot, and exits, `rabbitmq-setup` declares the RabbitMQ exchange and every context's queues and exits, and `keycloak-setup` brings the `kart` realm's settings up to date and exits; then `api`, `worker`, `scheduler` and `debezium` start. All three run on every `up` and change nothing when there is nothing new. MinIO joins when a later ticket needs it. `--wait` returns once `migrate`, `rabbitmq-setup` and `keycloak-setup` have succeeded, the infrastructure, `debezium` and the `api` pass their healthchecks, and the `worker` and `scheduler` are running. Then, with the users and passwords from `.env.example`:

| Service | URL |
|---|---|
| API health | http://localhost:8000/health |
| API docs (OpenAPI) | http://localhost:8000/docs |
| RabbitMQ management | http://localhost:15672 |
| Keycloak admin | http://localhost:8080 |
| Jaeger (traces) | http://localhost:16686 |
| Mailpit (every email sent) | http://localhost:8025 |
| Postgres | `localhost:5432` |

Keycloak imports the `kart` realm from `keycloak/kart-realm.json`, and `keycloak-setup` gives it its email, email verification, password reset and password policy, and lets an Account sign in with only an email and a password, also when the realm already exists. Keycloak's emails, such as a password reset link, land in Mailpit. The realm has one local account per role, each with its role as both name and password: `customer`, `seller` and `operator`. To call the API as one of them, get a token from the `kart-api` client and send it as `Authorization: Bearer <token>`:

```sh
curl -s http://localhost:8080/realms/kart/protocol/openid-connect/token \
  -d grant_type=password -d client_id=kart-api -d username=customer -d password=customer
```

A business signs up for a Seller Account with an email and a password. Keycloak emails it a link, which lands in Mailpit, and it can sign in, with its email as the username, once it has opened the link:

```sh
curl -s http://localhost:8000/v1/storefront/seller-accounts \
  -H 'Content-Type: application/json' -d '{"email": "shop@example.com", "password": "a-good-password"}'
```

Ports listen on localhost only. If one is already taken on your machine, publish it elsewhere by setting `POSTGRES_HOST_PORT`, `RABBITMQ_HOST_PORT`, `RABBITMQ_MANAGEMENT_HOST_PORT`, `KEYCLOAK_HOST_PORT`, `MAILPIT_HOST_PORT`, `JAEGER_HOST_PORT` or `API_HOST_PORT` in your shell or in `.env`, for example `POSTGRES_HOST_PORT=5434`. Follow the logs with `docker compose logs -f`. Stop the stack with `docker compose down`, and add `-v` to also delete the Postgres, RabbitMQ and Debezium data.

### Configuration

`.env.example` is the one place the local users, passwords and hosts are set, and Compose hands it to every container as it is:

- Postgres, RabbitMQ and Keycloak create their users from it, and Debezium Server connects with them.
- Every Kart process reads it at startup through `kart.app.settings`, which builds the database and RabbitMQ URLs from it. A process refuses to start if a value is missing. Postgres is reached on port 5432 unless `POSTGRES_PORT` says otherwise.
- `SMTP_*` say where email goes: Mailpit locally. In production, `.env` points them at Resend, as `.env.example` describes.

Every Kart process logs one JSON object per line and exports its traces to `OTEL_EXPORTER_OTLP_ENDPOINT`, the local Jaeger by default. Set it empty to export nothing. Errors go to Sentry only when `SENTRY_DSN` is set; locally it isn't.

To change a value without editing `.env.example`, put it in a `.env` file at the repository root. Git ignores that file, and Compose reads it after `.env.example`.

## Development

The checks run on your machine through [uv](https://docs.astral.sh/uv/). Running the app doesn't need it. The tests in `tests/database/` and `tests/shared/` start a throwaway Postgres, RabbitMQ and Debezium Server in Docker through testcontainers, so Docker must be running. Run `uv sync` once: uv installs Python 3.14 if needed, creates `.venv` and installs `kart` from `src/` in editable mode.

Code follows [`CODING_STANDARDS.md`](CODING_STANDARDS.md). The checks below enforce what a tool can, and review checks the rest. CI runs these on every pull request and on pushes to `main`:

| Check | Command |
|---|---|
| Formatting | `uv run ruff format --check .` (fix with `uv run ruff format .`) |
| Lint, including function size and complexity | `uv run ruff check .` |
| Types | `uv run ty check` |
| Context boundaries | `uv run lint-imports` |
| Dead code | `uv run vulture` |
| Duplication | `uv run pylint src tests` |
| All of the above | `scripts/static-checks.sh`, which CI runs |
| Tests | `uv run pytest` |
| Deployment | `docker compose up --build --wait` on an empty database, then a check that every context was migrated, the exchanges were declared, Debezium is reading the replication slot and the api's traces reach Jaeger |

`lint-imports` enforces the boundaries described in [`overview.md`](docs/architecture/overview.md#inside-a-context): a context imports another context only through its `contracts`, a `contracts` module never exposes its context's internals, contexts never import `kart.app`, only a context's `infrastructure` and `migrations` use the shared plumbing (`kart.shared.outbox`, `kart.shared.inbox`), and both the shared kernel and the `domain` packages of Ordering, Fulfilment and Offer stay free of FastAPI (and Starlette), SQLAlchemy and Pydantic. `tests/shared/kernel/` also runs `ty` on a sample module to prove that passing one kind of id where another is expected fails type checking. The contracts live in `pyproject.toml`, and `tests/architecture/` proves each one catches what it should.
