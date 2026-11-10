"""Who is calling: the Principal behind an access token, which is all other contexts see of an
Account. Only Identity knows the tokens come from Keycloak (ADR-0005)."""

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Protocol

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


class InvalidAccessTokenError(Exception):
    """The token is not a valid, unexpired Kart token for exactly one role."""


class IdentityUnavailableError(Exception):
    """The keys that sign access tokens can't be fetched, so no token can be checked."""


class AccessTokens(Protocol):
    def verify(self, token: str) -> Principal:
        """The Principal the token was issued to.

        Raises `InvalidAccessTokenError` unless it is a valid, unexpired Kart token for exactly
        one role, and `IdentityUnavailableError` if it can't be checked.
        """
        ...
