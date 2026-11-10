"""What Identity's use cases need from outside the process. The app hands each one an adapter
that implements it."""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from kart.contexts.identity.contracts import Role
    from kart.contexts.identity.domain.account import Account, Credentials
    from kart.shared.kernel.ids import AccountId


class EmailTakenError(Exception):
    """The identity provider already holds an Account with this email."""


class SignUpRefusedError(Exception):
    """The identity provider refused the Account, for example because its password policy
    refuses its password. The message says why."""


@dataclass(frozen=True, slots=True)
class ProviderAccount:
    """An Account as the identity provider holds it."""

    account_id: AccountId
    # In lower case, as the identity provider keeps every email.
    email: str
    # Only Kart's roles, not the ones the identity provider gives every Account.
    roles: frozenset[Role]
    email_verified: bool


class IdentityProvider(Protocol):
    """Where Accounts sign in, and which emails them to verify their address (ADR-0005)."""

    def create_seller(self, credentials: Credentials) -> ProviderAccount:
        """A new Seller Account, signed in with its email, which it must verify first.

        Raises `EmailTakenError` if an Account has the email, and `SignUpRefusedError` if the
        identity provider refuses the Account.
        """
        ...

    def with_email(self, email: str) -> ProviderAccount | None:
        """The Account that has this email, if one has it."""
        ...

    def send_email_verification(self, account_id: AccountId) -> None:
        """Email the Account a link that verifies its email address."""
        ...


class AccountRepository(Protocol):
    """The Accounts Identity has registered, inside a Unit of Work."""

    def register(self, account: Account) -> None:
        """Record the Account and publish `account.registered.v1`, unless it is recorded
        already."""
        ...
