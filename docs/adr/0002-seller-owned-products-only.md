# Seller-owned Products only, no shared catalog in the MVP

noon's catalog has two kinds of product page: shared ones (NSKU), where many Sellers' Offers compete for the winning Offer, and Seller-owned ones (ZSKU), which only the creating Seller can sell. In the MVP every Product is Seller-owned: a Seller creates it, an Operator approves it, and it has exactly one Offer. A shared catalog would bring in catalog matching, content ownership disputes and the winning-Offer ranking, none of which the end-to-end loop needs. The cost is that the best-known part of noon's product page, Sellers competing on one Product, is missing until `Later`.

## Consequences

Product and Offer stay separate even though each Product has exactly one Offer. That way shared Products can be added later without remodelling.
