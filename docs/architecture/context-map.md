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
| **Payment** | Generic | Card payments, partial refunds, Cash on Delivery collection |
| **Notification** | Generic | Emails to Customers and Sellers |

External system: the **sandbox payment gateway** (Stripe test mode). The courier is simulated inside Fulfilment (see [`overview.md`](overview.md#shipments)), so it isn't a separate system in the MVP.

Core contexts get rich domain models. Supporting and generic contexts stay as thin as their job allows. Catalog moves to Core when shared Products ([ADR-0002](../adr/0002-seller-owned-products-only.md)) bring catalog matching.

## Map

The map is drawn as an animated diagram in [`diagrams/context-map.html`](diagrams/context-map.html). Arrows point from upstream to downstream (the downstream context depends on the upstream one). Solid lines are synchronous calls through a context's published interface; dashed lines are integration events. The relationships table below is the source of truth. Any change to it also updates the diagram, in the same commit (see [`diagrams/README.md`](diagrams/README.md)).

## Relationships

| Upstream → downstream | Relationship | Integration |
|---|---|---|
| Identity → every context | Open host service and published language; downstream conforms | Verified OIDC token carrying an Account id and one role; `account.registered` |
| Seller Onboarding → Catalog, Offer, Discovery, Seller Settlement | Downstream conforms | `seller.approved`, carrying the Seller's display name. Catalog refuses Products from Sellers who aren't approved |
| Catalog → Offer | Downstream conforms | `product.approved`, `product.rejected`. An Offer is live only when its Product is approved and price and stock are above zero |
| Catalog, Offer → Discovery | Downstream conforms (read model) | Events that carry state, plus snapshot queries to rebuild the read model |
| Offer → Ordering | Customer–supplier (Ordering is the customer) | Synchronous: query Offers, reserve stock for an Order (all lines or none, idempotent per Order), release an Order's reservation when checkout gives up. Event: Offer releases stock on `order.cancelled`, `shipment.cancelled` and `shipment.rejected` |
| Catalog → Ordering | Customer–supplier | Synchronous query at checkout for Product title, image, Category and Referral Fee rate, which are copied onto the Order line |
| Payment → Ordering | Open host service | Synchronous: start a card payment; cancel it before an unpaid Order is cancelled. Event: `payment.succeeded`. A declined card is retried within the payment window, so there is no failure event |
| Ordering → Fulfilment | Customer–supplier | `order.confirmed`, carrying lines grouped by Seller, with the `ShipmentId`, Shipment number and Estimated Delivery Date Ordering fixed for each group. Fulfilment creates one Shipment per group with those ids |
| Fulfilment → Offer, Payment, Ordering, Seller Settlement | Published language | `shipment.cancelled` / `shipment.rejected` (release stock, refund card payments, record the outcome on the Order, no Settlement); `shipment.delivered` (Settlement becomes final, Cash on Delivery recorded as collected) |
| Ordering, Fulfilment → Seller Settlement | Downstream conforms | Order lines with the Referral Fee rate, then the Shipment's outcome |
| Every context → Notification | Downstream conforms | Reacts to events; keeps its own copy of email addresses from `account.registered` |
| Payment ↔ Stripe | Anti-corruption layer | PaymentIntents, refunds, webhooks. No Stripe concept leaks out of Payment |

Ordering never reads Discovery at checkout. Discovery is an eventually consistent read model for Customers. Checkout asks the contexts that own the data.

## Shared kernel

Kept deliberately minimal; anything added needs a reason:

- `Money`: AED in minor units, with 5% VAT rules.
- Typed ids: `AccountId`, `SellerId`, `ProductId`, `OfferId`, `OrderId`, `ShipmentId`, `CategoryId`.
- The integration-event envelope (id, type, version, time it happened, trace context).

Everything else belongs to one context, even if it looks duplicated.
