# Kart: system architecture

How the Kart MVP backend is built, deployed and wired together. The contexts and their relationships are in [`context-map.md`](context-map.md). The frontend is out of scope for now; the backend is designed API first.

## Shape

One modular monolith with strict bounded-context boundaries ([ADR-0003](../adr/0003-modular-monolith-with-strict-context-boundaries.md)). The courier is simulated inside Fulfilment.

- **Language and frameworks:** Python, FastAPI, SQLAlchemy 2.0, Alembic, Pydantic.
- **Tooling:** uv, ruff, ty, pytest, import-linter.
- **Infrastructure:** Postgres (logical replication enabled), RabbitMQ, Debezium Server, Keycloak, S3-compatible object storage.

## Repository layout

```
pyproject.toml                  the kart package, tool config and import-linter contracts
Dockerfile                      the one image every Kart process runs from
src/kart/
  shared_kernel/                Money, typed ids, event envelope
  building_blocks/              technical plumbing contexts' adapters build on: the outbox table and writer
  contexts/                     one package per bounded context
    identity/                   Keycloak integration, token verification
    seller_onboarding/
    catalog/
    offer/
    discovery/
    ordering/
    fulfilment/
    payment/
    seller_settlement/
    notification/
    <context>/migrations/       each context's Alembic history
  app/                          process entrypoints (api, worker, scheduler, migrate, topology), settings, the shared engine and unit of work, and the Alembic environment every history runs in
tests/                          architecture tests for the context boundaries, shared kernel and app tests, database tests against a real Postgres, the outbox end to end against Postgres, Debezium Server and RabbitMQ, and more to come
.env.example                    the local configuration, read by Compose as it is
deploy/                         Compose file and Debezium Server config
```

Kart is one package. The bounded contexts are kept apart by import-linter, not by packaging, so there is no uv workspace.

## Inside a context

Each context exposes exactly one importable surface, `contracts`: its synchronous commands and queries, their data objects, and its integration event schemas. import-linter fails CI on any import of another context's internals. Every package under `kart.contexts` must be independent of the others except through their `contracts`. A `contracts` module never imports its own context's `domain`, `application`, `infrastructure` or `api`: the internals implement the contracts, so the contracts can't leak them. Contexts may import `kart.shared_kernel` but never `kart.app`. `kart.building_blocks` holds technical plumbing with no domain meaning, such as the outbox; only a context's `infrastructure` and `migrations` may import it, and it imports no context. The shared kernel imports no context and, like a Core `domain`, no FastAPI, Starlette, SQLAlchemy or Pydantic.

How much layering a context gets depends on its subdomain:

- **Core (Ordering, Fulfilment, Offer):** hexagonal. `domain` (pure Python: no FastAPI, Starlette, SQLAlchemy or Pydantic imports), `application` (use cases and ports), `infrastructure` (repositories, imperative SQLAlchemy mapping, adapters), `api` (FastAPI routers).
- **Supporting and generic:** thin service plus repository code, still behind `contracts`.

## Data

- One Postgres database, **one schema per context**. A context never reads or writes another context's schema, and no transaction spans contexts.
- **One Alembic migration history per context**, each scoped to its own schema with its own version table. `python -m kart.app.migrate` runs them all, as the one-shot `migrate` service on every `docker compose up`.
- **One Postgres role per context**, which owns the context's schema. The app shares one engine, and each unit of work runs as its context's role, so Postgres refuses any statement that touches another context's schema ([ADR-0008](../adr/0008-a-postgres-role-per-context.md)).
- Product images go to object storage, owned by Catalog. Sellers upload through presigned URLs, and Postgres keeps only the object keys. MinIO runs locally; S3 or Cloudflare R2 in production.
- Discovery's search uses Postgres full-text search (`tsvector`) and `pg_trgm` for autocomplete, inside Discovery's own schema.

## Messaging

Integration events use a transactional outbox, relayed by change data capture (CDC) to RabbitMQ ([ADR-0004](../adr/0004-rabbitmq-with-transactional-outbox.md)).

1. A context writes its integration events to its own `<schema>.outbox` table in the same transaction as the state change, and deletes them in the same transaction. The rows exist only in the write-ahead log.
2. **Debezium Server** reads committed outbox inserts from the WAL (`pgoutput`, one connector and one publication covering every outbox table). Its Outbox Event Router publishes each event to the `kart.events` topic exchange, with the event type as the routing key (for example `product.approved.v1`) and the event id in the `id` header. The message body is the whole event envelope as JSON.
3. Each subscribing context has its own queue (for example `fulfilment.q`), bound to the routing keys it cares about, with a dead-letter queue.
4. Consumers record handled event ids in their own `<schema>.inbox` table, in the same transaction as the reaction, so redelivery is harmless.

The outbox table follows Debezium's outbox layout: `id`, `aggregatetype`, `aggregateid`, `type`, and `payload`, which holds the whole envelope, trace context included. A context's first migration creates it with `kart.building_blocks.outbox.create_outbox_table()`, and its adapters write events with `write_to_outbox()`, inside the unit of work. `migrate` then adds every outbox to the `outbox` publication and creates the replication slot, and the one-shot `topology` service declares the `kart.events` exchange, so no event is lost before Debezium first connects or while it is down ([ADR-0009](../adr/0009-change-data-capture-setup-and-building-blocks.md)).

Integration events carry the state their subscribers need, and they are versioned. A breaking change publishes a new version (`.v2`) alongside the old one until every consumer has moved over. Domain events stay inside their context.

## Processes

One container image, run as several process types:

| Process | Does |
|---|---|
| `api` | FastAPI: all HTTP routes and webhooks |
| `worker` | RabbitMQ consumers, one consumer group per context's queue |
| `scheduler` | Sweepers: retry Orders stuck in *placing*; cancel card Orders still *awaiting payment* after 30 minutes (cancelling the card payment first); move simulated deliveries forward |
| `debezium` | Debezium Server (its own image): outbox → RabbitMQ |

## API

One versioned REST/JSON API with OpenAPI docs, organised by audience. Each route belongs to exactly one context, and each context mounts its own routers.

| Prefix | Audience | Contexts |
|---|---|---|
| `/v1/storefront/...` | Anyone | Discovery, Ordering (guest carts) |
| `/v1/customer/...` | Customer | Ordering (cart, addresses, checkout, Orders), Fulfilment (Shipment tracking and cancellation) |
| `/v1/seller/...` | Seller | Seller Onboarding, Catalog, Offer, Fulfilment (Shipment queue, pack, reject), Seller Settlement |
| `/v1/operator/...` | Operator | Seller Onboarding and Catalog approval queues, Catalog (Categories, Referral Fees), Discovery (curation), read-only views of Orders and Shipments |
| `/v1/webhooks/payments` | Stripe | Payment (signature-verified) |

Authentication uses Keycloak OIDC ([ADR-0005](../adr/0005-keycloak-for-identity.md)). The API verifies the JWT and checks its role against the audience prefix. Inside the app, contexts see only an Account id and a role.

## Key flows

An animated sequence of these flows is in [`diagrams/order-flow.html`](diagrams/order-flow.html). Any change to a flow also updates that diagram, in the same commit (see [`diagrams/README.md`](diagrams/README.md)).

### Checkout

Ordering coordinates checkout. The full design, including pricing rules, crash recovery and the Order's states, is in [`contexts/ordering.md`](contexts/ordering.md).

1. Re-price the Cart: query Offer (price, live status, Seller, Processing Time) and Catalog (title, image, Category, Referral Fee rate) through their `contracts`. If a line is unavailable or the total differs from the one the Customer saw, refuse with a fresh quote.
2. Save the Order as **placing**, with every amount fixed: item prices including VAT, a Delivery Charge per Seller's lines, the Cash on Delivery Fee on the most valuable Shipment's lines, and the Referral Fee rate per line. Ordering also creates each future Shipment's id here.
3. Call Offer synchronously to reserve stock for this Order: all lines or none, idempotent per Order id.
4. If the reservation fails, the Order is **failed** (out of stock).
   If it succeeds:
   - **Cash on Delivery:** the Order is **confirmed**.
   - **Card:** the Order is **awaiting payment**. Ordering asks Payment to start a card payment (a PaymentIntent for the full amount) and returns its client secret.
5. A crash between steps 2 and 4 leaves the Order in *placing*, and the scheduler retries it. Reservation is idempotent, so retrying is safe.

### Card payment

- A declined card doesn't end the Order: the Customer can try another card within 30 minutes.
- When Stripe's webhook reports success, Payment publishes `payment.succeeded` and Ordering confirms the Order.
- After 30 minutes unpaid, or if the Customer abandons payment, Ordering first asks Payment synchronously to cancel the card payment. If that works, Ordering cancels the Order and publishes `order.cancelled`, and Offer releases its stock. If the payment already succeeded, the Order waits for `payment.succeeded` instead.
- Payment is captured in full at checkout and refunded per Shipment.

### Shipments

- `order.confirmed` → Fulfilment creates one Shipment per Seller and Notification sends each Seller an email. Seller Settlement records each Shipment's gross amount and Referral Fee.
- The Seller marks the Shipment packed → Fulfilment books a pickup through its `Courier` port.
- In the MVP, the port's adapter is a **simulated courier inside Fulfilment**. It records the booking in Fulfilment's schema, and the `scheduler` moves the Shipment through shipped → out for delivery → delivered after configurable delays, by calling Fulfilment's own use cases. For Cash on Delivery, delivery records the full amount as collected.
- A real courier later is a new adapter behind the same port, plus a webhook route.
- `shipment.delivered` → Payment records any Cash on Delivery collected, Seller Settlement makes the Settlement final, Ordering records the Shipment's outcome on the Order, and Notification sends the Customer an email.
- Failed delivery and returns are `Later`; the courier simulates only the happy path.

### Cancellation and rejection

The flow is choreographed, with no orchestrator.

- A Customer can cancel a Shipment before it is packed, and a Seller can reject one. Either way, Fulfilment publishes `shipment.cancelled` or `shipment.rejected`, carrying the Shipment's lines and amount.
- Offer releases the lines' stock.
- For card Orders, Payment refunds the Shipment's items plus its Delivery Charge.
- Ordering records the Shipment's outcome on the Order.
- Seller Settlement discards the Shipment's Settlement.
- If that Shipment carried the Cash on Delivery Fee, the fee is waived.

## Observability

- OpenTelemetry traces and metrics. Trace context is stored with each outbox row and travels in RabbitMQ message headers, so one trace follows a request across contexts.
- Structured JSON logs.
- Exported to Grafana Cloud (free tier). Errors go to Sentry.
- Debezium replication lag and dead-letter queue depth are monitored.

## Environments and delivery

- **Local:** Docker Compose with Postgres, RabbitMQ, Debezium Server, Keycloak, MinIO, Mailpit and the app processes. `docker compose up` is the whole deployment: no setup before, no manual steps such as migrations after ([ADR-0007](../adr/0007-docker-compose-up-is-the-whole-deployment.md)).
- **Production:** one VM running Docker Compose, with Caddy for TLS. Email goes through Resend; payments use Stripe test mode.
- **CI/CD:** GitHub Actions runs ruff, ty, pytest and import-linter, builds the images, and deploys on merge to `main`.

## Deferred to later sessions

Tactical design of the remaining core contexts: Fulfilment, then Offer. Ordering's is in [`contexts/ordering.md`](contexts/ordering.md).
