# RabbitMQ with a CDC-relayed transactional outbox for integration events

Bounded contexts publish versioned integration events (for example `product.approved.v1`) that carry the state subscribers need. Each context writes its events to its own outbox table in the same transaction as the state change. Change data capture (CDC) relays them: Debezium Server reads committed outbox inserts from the Postgres write-ahead log and publishes them to a RabbitMQ topic exchange. No application process polls the outbox. Each subscribing context has its own queue with a dead-letter queue, and records handled event ids in an inbox table so that redelivery is harmless.

We chose RabbitMQ over Kafka because its routing matches how our contexts subscribe to each other, and we don't need a replayable log: Discovery rebuilds its read model from snapshot queries against Catalog and Offer, not by replaying events. We chose a broker over Postgres-only dispatch so the MVP runs real messaging infrastructure. The outbox stays because publishing straight to the broker inside a request can lose events or publish events for transactions that were rolled back.

We chose CDC over a polling relay because it publishes in commit order with low latency and puts no polling load on the database, at the cost of running a CDC connector and enabling logical replication.

## Consequences

- Delivery is at-least-once, so every consumer must be idempotent.
- Cross-context workflows (cancellation, rejection, payment failure) are choreographed through events. There is no central saga orchestrator.
- Postgres runs with logical replication enabled, and the CDC connector is a piece of infrastructure we operate and monitor.
- Moving to Kafka later changes only the connector's sink and the consumers' transport, not the contracts.
