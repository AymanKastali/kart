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

## Money

**Referral Fee**:
The marketplace's commission on each item sold, as a percentage set per Category.
_Avoid_: Commission, take rate, marketplace fee

**Delivery Charge**:
The amount a Customer pays for delivering one Shipment, which depends on that Shipment's value.
_Avoid_: Shipping fee, delivery fee
