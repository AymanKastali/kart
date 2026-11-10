"""A Seller's business details, submitted for an Operator's review."""

import re
from dataclasses import dataclass, replace
from enum import StrEnum
from typing import TYPE_CHECKING, NewType

from kart.shared.kernel.ids import SellerId

if TYPE_CHECKING:
    from kart.shared.kernel.ids import AccountId

# A UAE Tax Registration Number.
VatNumber = NewType("VatNumber", str)
Iban = NewType("Iban", str)

_VAT_NUMBER = re.compile(r"[0-9]{15}")
_UAE_IBAN = re.compile(r"AE[0-9]{21}")


def parse_vat_number(text: str) -> VatNumber:
    """Raises `ValueError` unless `text` is exactly 15 digits."""
    if not _VAT_NUMBER.fullmatch(text):
        msg = "A VAT number is exactly 15 digits"
        raise ValueError(msg)
    return VatNumber(text)


def parse_iban(text: str) -> Iban:
    """Raises `ValueError` unless `text` is a UAE IBAN, `AE` and 21 digits, with the right check
    digits."""
    if not _UAE_IBAN.fullmatch(text):
        msg = "An IBAN is a UAE one: AE followed by 21 digits"
        raise ValueError(msg)
    if not _check_digits_match(text):
        msg = "The IBAN's check digits don't match the rest of it"
        raise ValueError(msg)
    return Iban(text)


def _check_digits_match(iban: str) -> bool:
    # ISO 13616: the first four characters move to the end, each letter becomes two digits
    # (A is 10, through Z, 35), and the number they make is 1 more than a multiple of 97.
    rearranged = iban[4:] + iban[:4]
    return int("".join(str(int(character, 36)) for character in rearranged)) % 97 == 1


class Status(StrEnum):
    PENDING = "pending"


@dataclass(frozen=True, slots=True)
class BusinessDetails:
    legal_name: str
    display_name: str
    trade_licence_number: str
    vat_number: VatNumber
    iban: Iban


@dataclass(frozen=True, slots=True)
class SellerApplication:
    account_id: AccountId
    seller_id: SellerId
    details: BusinessDetails
    status: Status
    # Counts the changes, so a write based on an older one is refused.
    version: int

    def resubmitted(self, details: BusinessDetails) -> SellerApplication:
        """The Seller Application with the business details the Seller submitted again."""
        return replace(self, details=details, version=self.version + 1)


def first_submission(account_id: AccountId, details: BusinessDetails) -> SellerApplication:
    """The Seller Application a Seller submits for the first time, which makes it a Seller."""
    return SellerApplication(account_id, SellerId.new(), details, Status.PENDING, version=1)


class NoSellerApplicationError(Exception):
    """The Seller has submitted no Seller Application."""


class SellerApplicationChangedError(Exception):
    """Another write changed the Seller Application since it was read."""
