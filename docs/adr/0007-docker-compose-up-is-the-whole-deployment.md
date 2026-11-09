# `docker compose up` is the whole deployment

Kart is deployed by running one command, `docker compose up`, and nothing else. There are no setup steps beforehand and no manual steps afterwards: no copying config files, no running migrations, no importing realms, no creating queues. The stack is built in a production style. Every process runs from one image as a non-root user, services have healthchecks and restart policies, start in dependency order, and get their configuration from environment variables only.

The configuration is `.env.example`, which Compose reads as it is. An optional, git-ignored `.env` overrides it, for example with real secrets on a server. We rejected a required `cp .env.example .env` step, because it is exactly the kind of manual setup this rule removes.

## Consequences

- Anything the app needs before it can serve runs inside `compose up`: database migrations (#5) as a one-shot service that the app processes wait on (`service_completed_successfully`), and later Keycloak's realm import (#8), Debezium's configuration (#6) and RabbitMQ's queues. A README step that someone has to run by hand is a bug.
- Migrations and other start-up work must be safe to run on every `up`: running them twice is a no-op.
- Development tooling (uv, ruff, ty, pytest, import-linter) still runs on the developer's machine. This rule is about deploying and running the app, not about how it is developed.
