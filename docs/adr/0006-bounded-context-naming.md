# Bounded contexts are named for the capability they own, in the singular

DDD sets no rule on singular versus plural context names, and well-known examples mix both. Kart did too: Payments and Notifications were plural, and everything else was singular. We name a context for the business capability it owns, in the singular: an activity (Ordering, Fulfilment, Discovery, Seller Onboarding, Seller Settlement) or a noun for the capability (Catalog, Identity, Payment, Notification). The code uses the same name in snake_case (`kart.contexts.seller_onboarding`). Payments and Notifications became Payment and Notification.

Offer is a deliberate exception. Its name matches the Offer aggregate it owns, so "Offer" can mean either one. We considered Offer Management, Inventory and Merchandising, and kept Offer because it is the word the domain uses: a Seller's Offer is what this context manages. Inventory is a word `GLOSSARY.md` avoids, and Merchandising doesn't cover stock.

## Consequences

- When the context is meant, the docs say "the Offer context". A plain "Offer" means the aggregate.
- REST paths are resource names, not context names, and stay plural where that reads naturally (for example `/v1/webhooks/payments`).
