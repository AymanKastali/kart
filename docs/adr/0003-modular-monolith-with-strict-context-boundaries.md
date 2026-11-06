# Modular monolith with strict bounded-context boundaries

Kart's backend is a single deployable (Python, FastAPI, Postgres) split into bounded contexts with strict boundaries: each context owns its own Postgres schema, never reads another context's tables, and integrates with other contexts only through their published interfaces and events. We chose this over microservices because microservices would bring distributed deployment, per-service pipelines and network failure handling, none of which teach the marketplace domain. We chose it over a loosely-structured monolith because the project exists to practise DDD, and boundaries that are only conventions erode.

The courier is simulated inside Fulfilment, behind a port, rather than run as a separate service. A real courier can be added later as another adapter.

## Consequences

- Cross-context consistency is eventual and goes through events, even though everything shares one database server. We accept the extra work (outbox, idempotent consumers, compensations) in exchange for contexts that could be extracted into services later.
- Work is backend and API first; the frontend is deferred.
