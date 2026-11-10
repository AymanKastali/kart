"""Kart's Accounts as Keycloak holds them, created through its admin API."""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import httpx

from kart.contexts.identity.contracts import Role
from kart.contexts.identity.keycloak import admin_client
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


class KeycloakAccounts:
    def __init__(self, admin: KeycloakAdminLogin) -> None:
        self._admin = admin

    def create_seller(self, credentials: Credentials) -> KeycloakAccount:
        """A new Seller Account, signed in with its email, which it must verify first."""
        with admin_client(self._admin) as admin_api:
            response = admin_api.post("/users", json=_unverified_account(credentials))
            _raise_if_refused(response)
            account_id = AccountId(response.headers["Location"].rsplit("/", 1)[-1])
            _give_seller_role(admin_api, account_id)
        return KeycloakAccount(account_id, credentials.email.lower(), frozenset({Role.SELLER}))

    def with_email(self, email: str) -> KeycloakAccount:
        """The Account that has this email."""
        with admin_client(self._admin) as admin_api:
            [account] = (
                admin_api.get("/users", params={"email": email, "exact": "true"})
                .raise_for_status()
                .json()
            )
            roles = admin_api.get(f"/users/{account['id']}/role-mappings/realm").raise_for_status()
        return KeycloakAccount(
            AccountId(account["id"]),
            account["email"],
            frozenset(Role(role["name"]) for role in roles.json() if role["name"] in Role),
        )

    def make_seller(self, account_id: AccountId) -> None:
        with admin_client(self._admin) as admin_api:
            _give_seller_role(admin_api, account_id)

    def send_email_verification(self, account_id: AccountId) -> None:
        """Email the Account a link that verifies its email address."""
        with admin_client(self._admin) as admin_api:
            admin_api.put(f"/users/{account_id}/send-verify-email").raise_for_status()


def _unverified_account(credentials: Credentials) -> dict:
    return {
        "username": credentials.email,
        "email": credentials.email,
        "enabled": True,
        # Keycloak refuses to sign the Account in until the email is verified.
        "requiredActions": ["VERIFY_EMAIL"],
        "credentials": [{"type": "password", "value": credentials.password, "temporary": False}],
    }


def _give_seller_role(admin_api: httpx.Client, account_id: AccountId) -> None:
    seller_role = admin_api.get(f"/roles/{Role.SELLER}").raise_for_status().json()
    admin_api.post(
        f"/users/{account_id}/role-mappings/realm", json=[seller_role]
    ).raise_for_status()


def _raise_if_refused(response: httpx.Response) -> None:
    if response.status_code == httpx.codes.CONFLICT:
        raise EmailTakenError
    if response.status_code == httpx.codes.BAD_REQUEST:
        refusal = response.json()
        # A refused password comes with a description; a refused field, with a message.
        raise SignUpRefusedError(refusal.get("error_description") or refusal["errorMessage"])
    response.raise_for_status()
