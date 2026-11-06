# Kart: feature inventory and MVP

The full noon.com (UAE) feature set as of late 2026, each feature tagged with where it sits in Kart. Domain terms follow [`GLOSSARY.md`](../../GLOSSARY.md). Research sources are noon's customer help centre (help.noon.com) and seller help centres (helpcenter.noon.partners, support.noon.partners). noon's own names for things are given in brackets.

**Tags**

- `MVP`: in the first release.
- `Later`: a noon feature Kart will build after the MVP.
- `Out of scope`: not planned for Kart.

## The MVP

**Goal:** one complete, believable marketplace loop.

1. A Seller signs up and an Operator approves them.
2. The Seller creates a Product, an Operator approves it, and it gets listed with an Offer.
3. A Customer finds the Product, checks out a cart that spans several Sellers, and pays by card or Cash on Delivery.
4. The Order splits into one Shipment per Seller, and each Shipment moves on to delivery by itself.

**Constraints**

- **"Production-ready" means:**
  - deployed publicly, with real authentication, CI/CD, tests and observability;
  - payments go through a sandbox gateway (no real money);
  - the courier is simulated.
- **Platform:** responsive web only.
- **Market:** English only (see [ADR-0001](../adr/0001-english-only-no-rtl.md)), UAE only, prices in AED.
- **Actors:** Customer, Seller and Operator.
- **Catalog:** every Product is created and owned by one Seller, who is the only one who can sell it (noon's ZSKU model). There are no shared Products in the MVP (see [ADR-0002](../adr/0002-seller-owned-products-only.md)).
- **Products and Offers stay separate:** the Product holds the approved content, and the Offer holds price, stock and Processing Time.
- **Variants:** each variant is its own Product.
- **Fulfilment:** the Seller packs each Shipment and a simulated courier delivers it (noon's Directship model).

---

## 1. Customer

### 1.1 Account and identity

| Feature | Tag | Notes |
|---|---|---|
| Sign up and log in with email and password, verify email, reset password | `MVP` | noon uses an email one-time code (OTP) |
| Browse and fill a cart without an account; signing in is required to check out | `MVP` | |
| Log in with phone and SMS code | `Later` | |
| Social login (Google, Apple) | `Later` | unverified on noon |
| One account across noon verticals (super-app) | `Out of scope` | |

### 1.2 Addresses

| Feature | Tag | Notes |
|---|---|---|
| Address book of UAE addresses (emirate, area, street/building, apartment, phone) with a default address | `MVP` | |
| Map pin for addresses | `Later` | |
| Code-verified address changes | `Later` | |
| Delivery lockers, gift addresses | `Later` | |

### 1.3 Discovery

| Feature | Tag | Notes |
|---|---|---|
| Home page of Operator-curated Categories and Products | `MVP` | |
| Browse by Category | `MVP` | |
| Keyword search with autocomplete | `MVP` | |
| Filters for Category, price range and Seller | `MVP` | |
| Sort by price and by newest | `MVP` | |
| Filters for brand, colour, rating, noon Express and new arrivals | `Later` | |
| Deal pages and flash deals with countdowns | `Later` | |
| Recently viewed, personalised recommendations | `Later` | unverified on noon |
| Voice search | `Out of scope` | unverified on noon |

### 1.4 Product page

| Feature | Tag | Notes |
|---|---|---|
| Title, images, description, highlights, specs, brand, Category | `MVP` | specs are free-form key/value pairs |
| Price including VAT, stock status, Seller name | `MVP` | |
| Estimated Delivery Date ("Get it by") | `MVP` | order date + Processing Time + fixed UAE delivery time |
| Variant picker (size, colour) | `Later` | noon groups variants under a parent |
| Product video | `Later` | |
| Several Sellers' Offers on one Product, winning Offer, "View All Offers" | `Later` | noon's NSKU and buy box; needs shared Products |
| Warranty type on the Offer (Seller, brand, none) | `Later` | |
| Badges: noon Express, Global, Supermall, deal | `Later` | |
| Urgency signals ("only N left", "X sold recently", "lowest price in 30 days") | `Later` | unverified wording |
| Product reviews from verified buyers, with a report button | `Later` | |
| Seller rating stars | `Later` | |
| Customer questions and answers | `Out of scope` | unverified on noon |

### 1.5 Cart and wishlist

| Feature | Tag | Notes |
|---|---|---|
| One cart holding Products from many Sellers | `MVP` | items in a cart don't hold stock |
| Wishlists (several, named, private or shared) | `Later` | |
| Save for later | `Later` | unverified on noon |
| Coupons and promo codes | `Later` | |
| Coupon cashback paid as credits | `Later` | |

### 1.6 Checkout and payment

| Feature | Tag | Notes |
|---|---|---|
| Card payment through a sandbox gateway | `MVP` | |
| Cash on Delivery: AED 12 Cash on Delivery Fee, not available above AED 6,500 | `MVP` | the fee is collected with the most valuable Shipment and waived if that Shipment is cancelled or rejected |
| Delivery Charge per Shipment: under AED 100 → AED 10; AED 100–500 → AED 5; over AED 500 → free | `MVP` | |
| Prices include 5% VAT, with VAT shown separately on the Order | `MVP` | |
| Stock reduced when the Order is placed; released on cancellation, rejection or failed card payment | `MVP` | |
| Apple Pay | `Later` | |
| Pay with noon credits, alone or combined with card or Cash on Delivery | `Later` | |
| Buy-now-pay-later (Tabby, Tamara), bank instalments | `Later` | |
| Bank offers and co-branded cards | `Out of scope` | |
| Cash on Delivery blocks for abuse, prepaid-only items | `Later` | |
| Delivery speeds: same-day, next-day, bulky items | `Later` | |

### 1.7 Orders and tracking

| Feature | Tag | Notes |
|---|---|---|
| Order history and Order detail | `MVP` | |
| Tracking per Shipment, with status and Estimated Delivery Date | `MVP` | |
| Cancel a Shipment before it's packed, with automatic card refund | `MVP` | |
| Cancel after packing (Pending Cancellation) | `Later` | |
| Tax invoice download | `Later` | |

### 1.8 Returns, refunds and warranty

| Feature | Tag | Notes |
|---|---|---|
| 15-day returns with a reason | `Later` | |
| Refund to card; Cash on Delivery refunds go to credits | `Later` | |
| "Track Refund" | `Later` | |
| Returnless refund | `Later` | |
| Warranty claims | `Later` | |
| Supermall "2X refund" on counterfeits | `Out of scope` | |

### 1.9 Loyalty and wallet

| Feature | Tag | Notes |
|---|---|---|
| noon credits wallet (balance, expiry, pending) | `Later` | |
| Transfer credits to a bank account | `Later` | |
| Gift cards | `Later` | |
| Referral programme | `Later` | unverified mechanics |
| Cashback | `Later` | |
| noon One paid membership (free delivery thresholds, early sale access) | `Later` | |

### 1.10 Support and notifications

| Feature | Tag | Notes |
|---|---|---|
| Email on every Shipment status change (placed, shipped, delivered, cancelled) | `MVP` | |
| Push and SMS notifications | `Later` | |
| Help centre and order-specific help | `Later` | |
| Live chat with customer service | `Later` | |
| Delivery reviews | `Later` | |

### 1.11 Sales events

| Feature | Tag | Notes |
|---|---|---|
| Sale events (11.11, Yellow Friday, Ramadan), Mega Deals, buy-one-get-one, bundles | `Later` | |
| Early access to sales for members | `Later` | |

---

## 2. Seller (noon's "Seller Lab")

### 2.1 Onboarding

| Feature | Tag | Notes |
|---|---|---|
| Sign up with business details (trade licence number, VAT number, IBAN) entered as plain fields | `MVP` | |
| Operator approval before the Seller can list anything | `MVP` | |
| Document upload and identity checks (trade licence, Emirates ID, bank proof) | `Later` | |
| Brand registration and gated brands or categories | `Later` | |
| Cross-border (Global) sellers | `Out of scope` | |

### 2.2 Catalog

| Feature | Tag | Notes |
|---|---|---|
| Create a Product (title, images, description, highlights, specs, brand, Category) | `MVP` | noon's ZSKU |
| Product starts as pending; Operator approves it or rejects it with a reason; the Seller fixes and resubmits | `MVP` | |
| Edit own Product content, live without re-approval | `MVP` | |
| The Seller's own product identifier (PSKU) | `MVP` | |
| Offer on each Product: price, stock, Processing Time (1–10 days) | `MVP` | |
| An Offer is live only when its Product is approved and price and stock are both above zero | `MVP` | |
| Attach an Offer to a shared Product (NSKU) | `Later` | |
| Parent/child variants | `Later` | |
| Bulk create and update by spreadsheet (catalog, price, stock) | `Later` | |
| Prohibited keyword screening | `Later` | |
| Channel-manager API integrations | `Out of scope` | |

### 2.3 Fulfilment

| Feature | Tag | Notes |
|---|---|---|
| New-Shipment queue, with an email for each new Shipment | `MVP` | |
| Mark a Shipment packed / ready for handover | `MVP` | |
| Reject a Shipment it can't fill, which refunds and releases stock | `MVP` | |
| Simulated courier takes the Shipment from shipped to delivered | `MVP` | |
| Shipments packed but not handed over are cancelled automatically after the estimated ship date | `Later` | |
| Pick-up or drop-off at a hub | `Later` | |
| Fulfilled by noon (FBN): advance shipping notice, warehouse appointments, quality check, storage | `Later` | |
| noon Express badge | `Later` | |
| Bulky Directship, Direct Delivery with the Seller's own fleet | `Out of scope` | |

### 2.4 Returns (Seller side)

| Feature | Tag | Notes |
|---|---|---|
| Customer return dashboard | `Later` | |
| Return grading (A–X) and Seller compensation | `Later` | |
| Return administration fee | `Later` | |

### 2.5 Money

| Feature | Tag | Notes |
|---|---|---|
| Referral Fee per Category, recorded on each sold item | `MVP` | |
| Gross sales, Referral Fee and net amount per Shipment | `MVP` | |
| Weekly statements and payouts | `Later` | |
| Monthly statement of account, fee invoices | `Later` | |
| Outbound, storage, cancellation and penalty fees | `Later` | |
| Fees and revenue calculator | `Later` | |

### 2.6 Growth and performance

| Feature | Tag | Notes |
|---|---|---|
| Join deal events | `Later` | |
| noon ads: sponsored Products (pay per click) | `Later` | |
| Brand and display ads | `Out of scope` | |
| Account health: cancellation rate, late shipment rate | `Later` | |
| Penalties (stock pulldown, Offer deactivation, suspension) and plan of action | `Later` | |
| Reputation dashboard (ratings, reviews) | `Later` | |

---

## 3. Operator

| Feature | Tag | Notes |
|---|---|---|
| Seller approval queue | `MVP` | |
| Product approval queue (approve, or reject with a reason) | `MVP` | |
| Category tree management, including the Referral Fee per Category | `MVP` | |
| Home-page curation | `MVP` | |
| Read-only view of Orders and Shipments | `MVP` | |
| Shared Product (NSKU) content management | `Later` | |
| Winning-Offer ranking rules | `Later` | |
| Merge duplicate Products | `Later` | |
| Seller performance enforcement | `Later` | |
| Review moderation | `Later` | |
| Customer-service tooling (cancellations, refunds, returns approval) | `Later` | |
| Fraud controls (Cash on Delivery limits, credit abuse, high-value refund checks) | `Later` | |
| Coupon, cashback and sale-event campaigns | `Later` | |
| Finance: statement generation, payouts, seller compensation | `Later` | |
| Warehouses, hubs and own delivery fleet | `Out of scope` | simulated courier only |

---

## 4. Platform-wide

| Feature | Tag | Notes |
|---|---|---|
| English UI | `MVP` | |
| UAE storefront, AED | `MVP` | |
| Arabic UI and right-to-left layout | `Out of scope` | [ADR-0001](../adr/0001-english-only-no-rtl.md) |
| KSA and Egypt storefronts (SAR, EGP) | `Later` | |
| Kuwait, Qatar, Oman, Bahrain cross-border selling | `Out of scope` | |
| Native iOS and Android apps | `Later` | |

---

## 5. Other noon verticals: out of scope

Each is a separate product with its own domain. They're listed only for completeness.

- **noon Minutes**: 15-minute quick commerce from dark stores.
- **NowNow**: under-60-minute delivery from partner supermarkets and pharmacies.
- **noon Food**: restaurant food delivery.
- **noon Supermall**: brand-direct authentic store with 45–60-minute delivery.
- **noon Daily / noon Grocery**: next-day fresh groceries with subscribe-and-replenish.
- **noon Pay / noon payments**: a consumer wallet app, and a merchant payment gateway.
- **noon Global Store**: cross-border items with customs handled by noon.
- **noon send**: on-demand parcel delivery.
