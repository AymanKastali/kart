# Ordering: tactical design

Ordering is a Core context. It owns the Cart, the Address Book, checkout and the Order. Terms follow [`GLOSSARY.md`](../../../GLOSSARY.md). Its relationships with other contexts are in [`context-map.md`](../context-map.md), and how it is built (hexagonal layers, `contracts`, outbox) is in [`overview.md`](../overview.md#inside-a-context).

An animated diagram of the Order's states is in [`diagrams/order-lifecycle.html`](../diagrams/order-lifecycle.html). Any change to the state machine also updates that diagram, in the same commit (see [`diagrams/README.md`](../diagrams/README.md)).

## Aggregates

Three aggregates. Checkout reads the Cart and the Address Book and creates an Order; no invariant spans more than one of them.

### Cart

One per Customer, plus guest carts for signed-out visitors.

- A line is an **Offer id and a quantity**. No price is stored: the Cart always shows the current Offer price (VAT included) and whether the Offer is live.
- Quantity is 1 to 10 per line.
- A line whose Offer is no longer live stays in the Cart, marked unavailable. Quoting and checkout refuse until the Customer removes it.
- A guest cart is kept on the server, keyed by an anonymous cart id the client holds. On sign-in it is merged into the Customer's Cart: quantities for the same Offer are added and capped at 10, and the guest cart is deleted. A guest cart untouched for 30 days expires.
- When an Order is placed (stock reserved), the ordered lines are removed from the Cart. A Cart can't be checked out twice while a card payment is pending.

### Address Book

One per Customer.

- An address has an emirate (one of the seven), area, street or building, an optional apartment, and a UAE mobile number in the form `+9715XXXXXXXX`. It is not checked against a real map.
- At most 10 addresses. The first one saved is the default. Deleting the default makes the most recently added remaining address the default.

### Order

Everything a Customer bought in one checkout, with every amount fixed.

- The Order holds the copied delivery address, the payment method, and one **Seller group** per Seller.
- Each Seller group is a future Shipment. Ordering creates its `ShipmentId` and Shipment number at checkout, and Fulfilment creates the Shipment with them. A group holds its lines, its item value, its Delivery Charge, the Cash on Delivery Fee if it carries it, its Estimated Delivery Date, and, once confirmed, its **outcome**: open, delivered, cancelled or rejected.
- Each line holds the Offer id, Product id, title, image, Category, quantity, unit price including VAT, the VAT in it, and the Referral Fee rate.
- Groups are ordered by item value, highest first, with ties going to the lowest Seller id. Group 1 is the most valuable Shipment.
- **Amounts never change once the Order is placed.** A cancelled or rejected group, or a waived Cash on Delivery Fee, is recorded as the group's outcome; the totals stay as they were. Money actually charged, refunded or collected belongs to Payments.
- The Order uses optimistic concurrency: a version number checked on save. When two Shipment events for the same Order race, the losing consumer rolls back, its inbox row included, and the message is redelivered.

## Order Number

`OrderId` is an internal, time-ordered UUID. At checkout the Order also gets an **Order Number**: `KAE` followed by 9 characters from uppercase letters and digits without look-alikes (no `0`, `O`, `1`, `I`). A Shipment's number is the Order Number plus its group position, for example `KAE7F3K9Q2XM-2`.

## Order states

```
placing ──► failed                           stock not reserved
placing ──► confirmed                        Cash on Delivery
placing ──► awaiting payment ──► confirmed   payment.succeeded
                             └─► cancelled   timeout or abandoned; card payment cancelled first
confirmed ──► completed                      every Shipment ended, at least one delivered
confirmed ──► cancelled                      every Shipment ended, none delivered
```

- **Failed** Orders never had stock, payment or a Shipment. They are hidden from the Customer's Order history and shown in the Operator's view.
- **Cancelled** always means the Customer received nothing and pays nothing.
- After confirmation the Order tracks only each group's outcome, learned from `shipment.*` events. Each Shipment's own steps (packed, shipped, out for delivery) are Fulfilment's, and Customers track them through Fulfilment's API.

## Pricing

All Customer-facing amounts include 5% VAT: item prices, Delivery Charges and the Cash on Delivery Fee. Pricing is a pure domain service; the quote and checkout both use it.

- **VAT** in each amount is `amount × 5/105`, rounded half-up to the fil, and summed for the Order.
- **Delivery Charge** per Seller group, from its item value: under AED 100 → AED 10; AED 100 to 500 inclusive → AED 5; over AED 500 → free.
- **Cash on Delivery** is unavailable when item value plus Delivery Charges is above AED 6,500. Its fee, AED 12, goes on group 1 (the most valuable).
- **Estimated Delivery Date** per group: checkout date + the longest Processing Time among its lines + 2 days of UAE delivery. Card Orders count from checkout too.

## Checkout

### Quote

A stateless quote: the Customer sends an address and a payment method, and gets back every amount for the current Cart, plus any unavailable lines. Nothing is saved.

### Placing an Order

The request carries the address, the payment method, the total the Customer saw, and an **idempotency key**. A repeat with the same key returns the same Order, and its client secret for a card Order.

1. Re-price the Cart: query Offer (price, live status, Seller, Processing Time) and Catalog (title, image, Category, Referral Fee rate) through their `contracts`. If any line is unavailable, or the total differs from the one the Customer saw, refuse with a conflict and a fresh quote. Nothing is saved.
2. Save the Order as **placing**, with every amount fixed.
3. Ask Offer to reserve stock for the Order: all lines or none, idempotent per Order id.
4. If Offer reports out of stock, the Order is **failed**. Otherwise the ordered lines leave the Cart and:
   - **Cash on Delivery:** the Order is **confirmed**.
   - **Card:** the Order is **awaiting payment**. Ordering asks Payments to start a card payment for the full amount, idempotent per Order id, and returns its client secret.

### Recovering from crashes

The scheduler retries Orders left behind by a crash, using the amounts already saved and no new price check:

- An Order in **placing** for more than 1 minute is retried from step 3. After 5 failed attempts, Ordering asks Offer to release any reservation for the Order (idempotent, a no-op if none exists) and the Order becomes **failed** once Offer confirms. Until Offer answers, the release keeps being retried, so a failed Order never holds stock.
- An Order **awaiting payment** whose card payment never started is retried until it starts. If it still hasn't started when the 30-minute window ends, the Order is cancelled like any other unpaid Order.

## Card payment window

An Order awaiting payment has 30 minutes. A declined card does not end it: the Customer can try another card on the same payment.

It ends in one of three ways:

- `payment.succeeded` → **confirmed**.
- The 30 minutes run out → **cancelled** (`payment_timeout`).
- The Customer abandons payment → **cancelled** (`customer_abandoned`).

Before cancelling for either reason, Ordering asks Payments synchronously to **cancel the card payment**. If that works, the Order is cancelled and `order.cancelled` is published. If Payments reports the payment already succeeded, the Order is left alone and confirmed when `payment.succeeded` arrives. A late payment can never land on a cancelled Order.

## Events

The Order aggregate records domain events (for example `OrderConfirmed`, `ShipmentOutcomeRecorded`), plain Python inside Ordering. The application layer turns the ones other contexts need into integration events from Ordering's `contracts` and writes them to `ordering.outbox` in the same transaction.

### Published

| Event | When | Carries |
|---|---|---|
| `order.confirmed.v1` | The Order is confirmed | Order id, Order Number, Customer `AccountId`, payment method, delivery address. Per Seller group: `ShipmentId`, Shipment number, `SellerId`, Estimated Delivery Date, item value, Delivery Charge, Cash on Delivery Fee if carried, and lines (Offer id, Product id, title, quantity, unit price including VAT, VAT, Referral Fee rate) |
| `order.cancelled.v1` | Cancelled **before** confirmation | Order id and reason: `payment_timeout` or `customer_abandoned`. Offer releases the reservation by Order id |

An Order that ends **cancelled** or **completed** because its Shipments ended publishes nothing: every other context has already reacted to the Shipment events. Failed Orders publish nothing either.

### Consumed

| Event | Reaction |
|---|---|
| `payment.succeeded` | Awaiting payment → confirmed |
| `shipment.delivered` | Group outcome → delivered; Order may become completed |
| `shipment.cancelled`, `shipment.rejected` | Group outcome → cancelled or rejected; Order may become completed or cancelled |

## Calls to other contexts

All through the other context's `contracts`:

| Context | Call |
|---|---|
| Offer | Query Offers; reserve stock for an Order; release an Order's reservation |
| Catalog | Query Products: title, image, Category, Referral Fee rate |
| Payments | Start a card payment; cancel a card payment |

## API

| Route | Does |
|---|---|
| `POST /v1/storefront/carts` | Create a guest cart; returns its id |
| `GET /v1/storefront/carts/{cart_id}` | A guest cart, priced |
| `PUT`, `DELETE /v1/storefront/carts/{cart_id}/lines/{offer_id}` | Set a guest cart line's quantity, or remove it |
| `GET /v1/customer/cart` | The Customer's Cart, priced |
| `PUT`, `DELETE /v1/customer/cart/lines/{offer_id}` | Set a line's quantity, or remove it |
| `POST /v1/customer/cart/merge` | Merge a guest cart into the Customer's Cart |
| `GET`, `POST /v1/customer/addresses`; `PUT`, `DELETE /v1/customer/addresses/{id}` | Address Book |
| `POST /v1/customer/addresses/{id}/default` | Make an address the default |
| `POST /v1/customer/checkout/quote` | Stateless quote |
| `POST /v1/customer/orders` | Place an Order (`Idempotency-Key` header) |
| `GET /v1/customer/orders`, `GET /v1/customer/orders/{order_number}` | Order history (failed Orders hidden) and detail |
| `POST /v1/customer/orders/{order_number}/abandon-payment` | Abandon an unpaid card Order |
| `GET /v1/operator/orders`, `GET /v1/operator/orders/{order_number}` | Read-only view of every Order, failed ones included |
