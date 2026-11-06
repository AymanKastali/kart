# Kart

A learning and portfolio clone of the noon.com UAE e-commerce marketplace, where Sellers list their own Products and Customers buy from many Sellers in one checkout.

## Actors

**Customer**:
A person who browses the catalog and places orders.
_Avoid_: Buyer, shopper, user, client

**Seller**:
A business that sells products on the marketplace through the seller portal.
_Avoid_: Merchant, vendor, partner, store

**Operator**:
A member of the marketplace's own staff who runs the platform, for example by moderating the catalog, handling customer service or overseeing logistics.
_Avoid_: Admin, staff, employee

**Account**:
The login an actor uses to sign in, with exactly one role: Customer, Seller or Operator. A Seller has exactly one Account.
_Avoid_: User, login, profile

## Bounded contexts

**Identity**: Accounts, sign-in and roles.
**Seller Onboarding**: a Seller's business details and the Operator's approval of them.
**Catalog**: Product content, Categories, and the Operator's approval of Products.
**Offer**: price, stock and Processing Time, and whether an Offer is live.
**Discovery**: how Customers find Products (search, browse, Product page) and the Operator-curated home page.
**Ordering**: Cart, address book, checkout and the Order.
**Fulfilment**: each Shipment's journey from Seller to Customer.
**Payments**: card payments, refunds and Cash on Delivery collection.
**Seller Settlement**: what each Seller earns from each Shipment.
**Notifications**: emails to Customers and Sellers.

## Catalog

**Product**:
A sellable item that one Seller created and owns. It is listed in the catalog only after an Operator approves it, and only its owning Seller can sell it.
_Avoid_: Listing, item, SKU, ZSKU

**Offer**:
One Seller's terms (price and stock) for selling a particular Product.
_Avoid_: Listing, price, inventory

**Processing Time**:
The number of days a Seller commits to needing before a Shipment is ready to hand over, set on each Offer.
_Avoid_: Lead time, handling time, PT

**Category**:
A node in the Operator-managed tree that every Product belongs to exactly one of.
_Avoid_: Department, section, collection

## Ordering

**Order**:
Everything a Customer bought in one checkout.
_Avoid_: Purchase, transaction, basket

**Shipment**:
The part of an Order fulfilled by a single Seller, which moves through delivery on its own.
_Avoid_: Sub-order, package, consignment, parcel

**Estimated Delivery Date**:
The date a Customer is promised a Shipment will arrive, derived from the Offer's Processing Time plus delivery time.
_Avoid_: ETA, EDD, "Get it by" date

**Cash on Delivery**:
A payment method where the Customer pays the courier when the Shipment arrives.
_Avoid_: COD, pay on delivery

**Cash on Delivery Fee**:
A fee charged once per Order paid by Cash on Delivery and collected with exactly one of its Shipments, the most valuable one at checkout. It is waived if that Shipment never arrives.
_Avoid_: COD fee, handling fee

## Money

**Referral Fee**:
The marketplace's commission on each item sold, as a percentage set per Category.
_Avoid_: Commission, take rate, marketplace fee

**Settlement**:
The record of what a Seller earns from one Shipment: gross sales, Referral Fee and net amount. A cancelled or rejected Shipment has no Settlement.
_Avoid_: Payout, earnings, statement

**Delivery Charge**:
The amount a Customer pays for delivering one Shipment, which depends on that Shipment's value.
_Avoid_: Shipping fee, delivery fee
