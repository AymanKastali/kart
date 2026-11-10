"""Kart's Accounts as Keycloak holds them, created through its admin API."""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import httpx

from kart.contexts.identity.contracts import Role
from kart.contexts.identity.keycloak import SELLERS_GROUP, admin_client
from kart.shared.kernel.ids import AccountId

if TYPE_CHECKING:
    from kart.contexts.identity.keycloak import KeycloakAdminLogin


class EmailTakenError(Exception):
    """Keycloak already holds an Account with this email."""


class SignUpRefusedError(Exception):
    """Keycloak refused the Account, for example because the realm's password policy refuses
    its password. The message says why."""


@dataclass(frozen=True, slots=True)
class Credentials:
    """What an Account signs in with."""

    email: str
    password: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class KeycloakAccount:
    account_id: AccountId
    # In lower case, as Keycloak keeps every email.
    email: str
    # Only Kart's roles, not the ones Keycloak gives every Account.
    roles: frozenset[Role]
    email_verified: bool


class KeycloakAccounts:
    def __init__(self, admin: KeycloakAdminLogin) -> None:
        self._admin = admin

    def create_seller(self, credentials: Credentials) -> KeycloakAccount:
        """A new Seller Account, signed in with its email, which it must verify first."""
        with admin_client(self._admin) as admin_api:
            response = admin_api.post("/users", json=_unverified_seller(credentials))
            _raise_if_refused(response)
        account_id = AccountId(response.headers["Location"].rsplit("/", 1)[-1])
        return KeycloakAccount(
            account_id,
            credentials.email.lower(),
            frozenset({Role.SELLER}),
            email_verified=False,
        )

    def with_email(self, email: str) -> KeycloakAccount | None:
        """The Account that has this email, if one has it."""
        with admin_client(self._admin) as admin_api:
            accounts = (
                admin_api.get("/users", params={"email": email, "exact": "true"})
                .raise_for_status()
                .json()
            )
            if not accounts:
                return None
            [account] = accounts
            # Composite, so it includes the roles the Account's groups give it.
            roles = admin_api.get(
                f"/users/{account['id']}/role-mappings/realm/composite"
            ).raise_for_status()
        return KeycloakAccount(
            AccountId(account["id"]),
            account["email"],
            frozenset(Role(role["name"]) for role in roles.json() if role["name"] in Role),
            email_verified=account["emailVerified"],
        )

    def send_email_verification(self, account_id: AccountId) -> None:
        """Email the Account a link that verifies its email address."""
        with admin_client(self._admin) as admin_api:
            admin_api.put(f"/users/{account_id}/send-verify-email").raise_for_status()


def _unverified_seller(credentials: Credentials) -> dict:
    return {
        "username": credentials.email,
        "email": credentials.email,
        "enabled": True,
        "groups": [f"/{SELLERS_GROUP}"],
        # Keycloak refuses to sign the Account in until the email is verified.
        "requiredActions": ["VERIFY_EMAIL"],
        "credentials": [{"type": "password", "value": credentials.password, "temporary": False}],
    }


def _raise_if_refused(response: httpx.Response) -> None:
    # Keycloak also answers a conflict when another Account's username is the email.
    if response.status_code == httpx.codes.CONFLICT:
        raise EmailTakenError
    if response.status_code == httpx.codes.BAD_REQUEST:
        refusal = response.json()
        # A refused password comes with a description; a refused field, with a message.
        raise SignUpRefusedError(refusal.get("error_description") or refusal["errorMessage"])
    response.raise_for_status()
