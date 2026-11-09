# Migrate prepares change data capture, the envelope is the message, and building blocks hold the outbox

Change data capture (CDC) carries every context's outbox to RabbitMQ: Debezium Server reads committed outbox inserts from the write-ahead log ([ADR-0004](0004-rabbitmq-with-transactional-outbox.md)). Left to itself, Debezium creates its publication and replication slot when it first connects. Anything committed before that, or to an outbox added to the publication later, never reaches the slot, and is lost. So `python -m kart.app.migrate`, after it runs every context's history, creates the `outbox` publication, adds every `<context>.outbox` table to it, and creates the logical replication slot `<database>_outbox`. Debezium runs with `publication.autocreate.mode=disabled` and only reads them. The slot then holds the write-ahead log for every event committed while Debezium is down, and Debezium resumes from the offset it keeps in a volume. Slot names are shared by the whole Postgres server, so the slot is named after the database.

The `kart.events` topic exchange is declared in code by `python -m kart.app.rabbitmq_setup`, a one-shot Compose service that Debezium waits for. We tried a RabbitMQ definitions file first, but loading one at boot stops RabbitMQ from creating its default virtual host and user, so the file would have to carry the password that `.env.example` already sets.

The message body is the whole event envelope as JSON (event id, type, occurred at, trace context and payload), not just the payload, so a consumer gets everything in one place and `EventEnvelope.from_json` reads it back. The event id also goes in the `id` header, which Debezium writes as a JSON string.

The outbox table and its writer live in `kart.building_blocks`, a layer between the contexts and the shared kernel for technical plumbing with no domain meaning. Only a context's `infrastructure` and `migrations` may import it, besides `kart.app`, which wires the contexts together, so the domain and application layers stay free of persistence. A port for publishing events comes with the first context that publishes one.

## Consequences

- A replication slot that nobody reads keeps the write-ahead log forever. If Debezium stays down, Postgres's disk fills, so replication lag must be monitored.
- A context gets its outbox into the publication by running `migrate`, which Compose does on every `up` before any process that could write events starts.
- The trace context travels inside the body for now. Copying it into the `traceparent` header comes with tracing (#9). Debezium adds its own `traceparent` and `__debezium.context.*` headers.
