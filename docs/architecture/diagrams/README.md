# Architecture diagrams

Animated [archify](https://github.com/tt-a1i/archify) diagrams of the docs in [`docs/architecture/`](..). Open the `.html` files in a browser.

| Diagram | Source | Draws |
|---|---|---|
| [`context-map.html`](context-map.html) | [`context-map.archify.json`](context-map.archify.json) | The contexts and relationships in [`context-map.md`](../context-map.md) |
| [`order-flow.html`](order-flow.html) | [`order-flow.archify.json`](order-flow.archify.json) | The Checkout, Card payment, Shipments, and Cancellation and rejection flows in [`overview.md`](../overview.md#key-flows) |

## Keeping them in sync

The markdown docs are the source of truth. These diagrams must never disagree with them. Any change to a context, relationship, integration event or key flow updates the matching `.archify.json` and re-renders its `.html` **in the same commit**.

Re-render from the repo root:

```bash
ARCHIFY=~/.claude/skills/archify/bin/archify.mjs
node $ARCHIFY finalize architecture docs/architecture/diagrams/context-map.archify.json docs/architecture/diagrams/context-map.html --repo-root . --quality showcase --out-dir .archify/context-map
node $ARCHIFY finalize sequence docs/architecture/diagrams/order-flow.archify.json docs/architecture/diagrams/order-flow.html --repo-root . --quality standard --out-dir .archify/order-flow
```

Never edit the `.html` by hand: it is generated. Set `meta.repository.revision` to a commit that contains the docs being drawn.
