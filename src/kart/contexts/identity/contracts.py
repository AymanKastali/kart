"""Who is calling: what every other context sees of an Account."""

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kart.shared.kernel.ids import AccountId


class Role(StrEnum):
    CUSTOMER = "customer"
    SELLER = "seller"
    OPERATOR = "operator"


@dataclass(frozen=True, slots=True)
class Principal:
    """The Account behind a request, with its one role."""

    account_id: AccountId
    role: Role
