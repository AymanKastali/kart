# Trace context travels in the event envelope, not the `traceparent` header

One trace follows a request across contexts: the HTTP request, the transaction that writes an integration event to the outbox, and every consumer that handles the event. `write_to_outbox` writes the event inside a producer span and stamps that span's W3C trace context (`traceparent`, and `tracestate` when there is one) into the envelope's `trace_context`. The worker reads it back from the message body and handles the event in a consumer span that continues the trace.

We meant to copy it into the standard `traceparent` message header too, so tools that read headers could follow the trace without parsing the body. But Debezium Server's Outbox Event Router always writes its own `traceparent` header, starting a new root trace for every event, and that overwrites any header we place under the same name with `table.fields.additional.placement`. A `tracingspancontext` column, the router's own tracing settings (`tracing.span.context.field`, `tracing.with.context.field.only`) and `OTEL_SDK_DISABLED` left that header unchanged. Placing our context under another header name would only repeat what the body already carries, under a name no tool knows. So the body is the one place the trace context travels.

## Consequences

- Debezium's `traceparent` header names a trace nobody exports. Consumers must ignore it and read the envelope.
- An event published outside any span still gets a trace context: the producer span starts a new trace.
- A message whose body doesn't parse can't continue any trace, so the worker logs that failure without a trace id. A failed handler's log line carries the publisher's trace.
