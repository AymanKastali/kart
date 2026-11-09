# The quorum queue counts deliveries, and the worker dead-letters an event that fails its fifth delivery

A failed handler rolls back and the worker nacks the event back onto its context's queue, so it is retried. Something has to stop an event that always fails from being retried forever. Each context's queue is a RabbitMQ quorum queue, which counts how often it has handed a message out in the `x-acquired-count` header. When an event fails on its fifth delivery, the worker nacks it without requeueing, and the queue's dead-letter settings route it through the default exchange to `<context>.dlq`. Kart keeps no retry state of its own and never republishes.

We meant to let the queue's `x-delivery-limit` do the dead-lettering, but RabbitMQ 4 doesn't count an AMQP 0-9-1 nack with requeue against that limit, only deliveries that end some other way, such as a consumer that disconnects. So the limit never fired, and the worker reads the header instead.

## Consequences

- Retries are immediate, with no backoff. That suits the optimistic-concurrency conflicts Ordering expects, which clear on the next try, but a handler waiting on something slower burns its five attempts quickly.
- One event at a time per worker (prefetch 1), so a queue's events are handled in the order they arrive, apart from retries, which go to the back of the queue.
- Events in a dead-letter queue stay there until someone looks at them; nothing replays them yet.
- Every delivery counts, not only failed ones: a worker that crashes or loses its connection mid-event returns it to the queue, so such an event can reach the dead-letter queue after fewer than five handler failures.
- An event that can never be handled, because its body doesn't parse or its type has no handler, still takes five deliveries to reach the dead-letter queue.
- A queue's arguments are fixed once declared: RabbitMQ refuses to redeclare a queue with different ones. Changing them must still happen inside `compose up` ([ADR-0007](0007-docker-compose-up-is-the-whole-deployment.md)), so `topology` would declare a queue under a new name, bind it and let the old one drain, never ask someone to delete a queue by hand.
