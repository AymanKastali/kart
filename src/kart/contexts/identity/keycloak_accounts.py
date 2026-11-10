"""Kart's Accounts as Keycloak holds them, created through its admin API."""

from dataclasses import dataclass
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
    its password."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True, slots=True)
class KeycloakAccount:
    account_id: AccountId
    email: str
    # Only Kart's roles, not the ones Keycloak gives every Account.
    roles: frozenset[Role]


class KeycloakAccounts:
    def __init__(self, admin: KeycloakAdminLogin) -> None:
        self._admin = admin

    def create_seller(self, email: str, password: str) -> AccountId:
        """A new Seller Account, signed in with its email, which it must verify first."""
        with admin_client(self._admin) as realm:
            response = realm.post("/users", json=_unverified_account(email, password))
            _raise_if_refused(response)
            account_id = AccountId(response.headers["Location"].rsplit("/", 1)[-1])
            _give_seller_role(realm, account_id)
        return account_id

    def with_email(self, email: str) -> KeycloakAccount:
        """The Account that has this email."""
        with admin_client(self._admin) as realm:
            [account] = (
                realm.get("/users", params={"email": email, "exact": "true"})
                .raise_for_status()
                .json()
            )
            roles = realm.get(f"/users/{account['id']}/role-mappings/realm").raise_for_status()
        return KeycloakAccount(
            AccountId(account["id"]),
            account["email"],
            frozenset(Role(role["name"]) for role in roles.json() if role["name"] in Role),
        )

    def make_seller(self, account_id: AccountId) -> None:
        with admin_client(self._admin) as realm:
            _give_seller_role(realm, account_id)

    def send_email_verification(self, account_id: AccountId) -> None:
        """Email the Account a link that verifies its email address."""
        with admin_client(self._admin) as realm:
            realm.put(f"/users/{account_id}/send-verify-email").raise_for_status()


def _unverified_account(email: str, password: str) -> dict:
    return {
        "username": email,
        "email": email,
        "enabled": True,
        # Keycloak refuses to sign the Account in until the email is verified.
        "requiredActions": ["VERIFY_EMAIL"],
        "credentials": [{"type": "password", "value": password, "temporary": False}],
    }


def _give_seller_role(realm: httpx.Client, account_id: AccountId) -> None:
    seller_role = realm.get(f"/roles/{Role.SELLER}").raise_for_status().json()
    realm.post(f"/users/{account_id}/role-mappings/realm", json=[seller_role]).raise_for_status()


def _raise_if_refused(response: httpx.Response) -> None:
    if response.status_code == httpx.codes.CONFLICT:
        raise EmailTakenError
    if response.status_code == httpx.codes.BAD_REQUEST:
        refusal = response.json()
        # A refused password comes with a description; a refused field, with a message.
        raise SignUpRefusedError(refusal.get("error_description") or refusal["errorMessage"])
    response.raise_for_status()
