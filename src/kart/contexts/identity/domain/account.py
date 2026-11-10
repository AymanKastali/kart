"""A Kart Account: who signs in, with which one role."""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kart.contexts.identity.contracts import Role
    from kart.shared.kernel.ids import AccountId


@dataclass(frozen=True, slots=True)
class Credentials:
    """What an Account signs in with."""

    email: str
    password: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class Account:
    account_id: AccountId
    role: Role
    email: str
