# Kart: context map

The bounded contexts of the Kart MVP and how they relate. Terms follow [`GLOSSARY.md`](../../GLOSSARY.md). How the contexts are deployed and wired together is in [`overview.md`](overview.md).

## Subdomains and contexts

| Context | Subdomain | Owns |
|---|---|---|
| **Ordering** | Core | Cart, address book, checkout, the Order (prices, VAT, Delivery Charges, Cash on Delivery Fee and Referral Fee rate fixed at checkout) |
| **Fulfilment** | Core | Each Shipment's lifecycle: created, packed, shipped, out for delivery, delivered, cancelled, rejected |
| **Offer** | Core | Price, stock, stock reservations, Processing Time, whether an Offer is live |
| **Catalog** | Supporting | Product content, the Product approval workflow, the Category tree and each Category's Referral Fee, Product images |
| **Seller Onboarding** | Supporting | A Seller's business details and their approval by an Operator |
| **Discovery** | Supporting | Search, browse and Product page read models; Operator curation of the home page |
| **Seller Settlement** | Supporting | One Settlement per delivered Shipment |
| **Identity** | Generic (bought: Keycloak) | Accounts, sign-in, roles. See [ADR-0005](../adr/0005-keycloak-for-identity.md) |
| **Payments** | Generic | Card payments, partial refunds, Cash on Delivery collection |
| **Notifications** | Generic | Emails to Customers and Sellers |

External system: the **sandbox payment gateway** (Stripe test mode). The courier is simulated inside Fulfilment (see [`overview.md`](overview.md#shipments)), so it isn't a separate system in the MVP.

Core contexts get rich domain models. Supporting and generic contexts stay as thin as their job allows. Catalog moves to Core when shared Products ([ADR-0002](../adr/0002-seller-owned-products-only.md)) bring catalog matching.

## Map

Arrows point from upstream to downstream (the downstream context depends on the upstream one). Solid lines are synchronous calls through a context's published interface; dashed lines are integration events.

An animated version is in [`diagrams/context-map.html`](diagrams/context-map.html). Any change to this map also updates that diagram, in the same commit (see [`diagrams/README.md`](diagrams/README.md)).

```mermaid
flowchart LR
  subgraph External
    Gateway[Stripe test mode]
  end

  Identity
  SO[Seller Onboarding]
  Catalog
  Offer
  Discovery
  Ordering
  Payments
  Fulfilment
  SS[Seller Settlement]
  Notif[Notifications]

  Identity -. account.registered .-> Notif
  SO -. seller.approved .-> Catalog & Offer & Discovery & SS
  Catalog -. product.approved / rejected .-> Offer
  Catalog -. product events .-> Discovery
  Offer -. offer events .-> Discovery

  Offer -- "query offers, reserve stock" --> Ordering
  Catalog -- "query Product, Referral Fee rate" --> Ordering
  Payments -- "start card payment" --> Ordering
  Payments -. payment.succeeded / failed .-> Ordering

  Ordering -. order.confirmed .-> Fulfilment
  Ordering -. order.cancelled .-> Offer
  Ordering -. order.confirmed .-> SS

  Fulfilment -. shipment.cancelled / rejected .-> Offer & Payments & Ordering & SS
  Fulfilment -. shipment.delivered .-> Ordering & SS & Payments

  Payments <-- ACL --> Gateway

  Ordering & Fulfilment & SO & Catalog -. events .-> Notif
```

## Relationships

| Upstream → downstream | Relationship | Integration |
|---|---|---|
| Identity → every context | Open host service and published language; downstream conforms | Verified OIDC token carrying an Account id and one role; `account.registered` |
| Seller Onboarding → Catalog, Offer, Discovery, Seller Settlement | Downstream conforms | `seller.approved`, carrying the Seller's display name. Catalog refuses Products from Sellers who aren't approved |
| Catalog → Offer | Downstream conforms | `product.approved`, `product.rejected`. An Offer is live only when its Product is approved and price and stock are above zero |
| Catalog, Offer → Discovery | Downstream conforms (read model) | Events that carry state, plus snapshot queries to rebuild the read model |
| Offer → Ordering | Customer–supplier (Ordering is the customer) | Synchronous: query Offers, reserve stock for an Order (all lines or none, idempotent per Order). Event: Offer releases stock on `order.cancelled`, `shipment.cancelled` and `shipment.rejected` |
| Catalog → Ordering | Customer–supplier | Synchronous query at checkout for Product title, image, Category and Referral Fee rate, which are copied onto the Order line |
| Payments → Ordering | Open host service | Synchronous: start a card payment. Events: `payment.succeeded`, `payment.failed` |
| Ordering → Fulfilment | Customer–supplier | `order.confirmed`, carrying lines grouped by Seller. Fulfilment creates one Shipment per Seller |
| Fulfilment → Offer, Payments, Ordering, Seller Settlement | Published language | `shipment.cancelled` / `shipment.rejected` (release stock, refund card payments, update the Order's derived status, no Settlement); `shipment.delivered` (Settlement becomes final, Cash on Delivery recorded as collected) |
| Ordering, Fulfilment → Seller Settlement | Downstream conforms | Order lines with the Referral Fee rate, then the Shipment's outcome |
| Every context → Notifications | Downstream conforms | Reacts to events; keeps its own copy of email addresses from `account.registered` |
| Payments ↔ Stripe | Anti-corruption layer | PaymentIntents, refunds, webhooks. No Stripe concept leaks out of Payments |

Ordering never reads Discovery at checkout. Discovery is an eventually consistent read model for Customers. Checkout asks the contexts that own the data.

## Shared kernel

Kept deliberately minimal; anything added needs a reason:

- `Money`: AED in minor units, with 5% VAT rules.
- Typed ids: `AccountId`, `SellerId`, `ProductId`, `OfferId`, `OrderId`, `ShipmentId`, `CategoryId`.
- The integration-event envelope (id, type, version, time it happened, trace context).

Everything else belongs to one context, even if it looks duplicated.
