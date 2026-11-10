"""Keycloak as Identity's identity provider, through its admin API (ADR-0005)."""

from typing import TYPE_CHECKING

import httpx

from kart.contexts.identity.application.ports import (
    EmailTakenError,
    ProviderAccount,
    SignUpRefusedError,
)
from kart.contexts.identity.contracts import Role
from kart.contexts.identity.infrastructure.keycloak import SELLERS_GROUP, admin_client
from kart.shared.kernel.ids import AccountId

if TYPE_CHECKING:
    from kart.contexts.identity.domain.account import Credentials
    from kart.contexts.identity.infrastructure.keycloak import KeycloakAdminLogin


class KeycloakIdentityProvider:
    """Implements `IdentityProvider`."""

    def __init__(self, admin: KeycloakAdminLogin) -> None:
        self._admin = admin

    def create_seller(self, credentials: Credentials) -> ProviderAccount:
        with admin_client(self._admin) as admin_api:
            response = admin_api.post("/users", json=_unverified_seller(credentials))
            _raise_if_refused(response)
        account_id = AccountId(response.headers["Location"].rsplit("/", 1)[-1])
        return ProviderAccount(
            account_id,
            credentials.email.lower(),
            frozenset({Role.SELLER}),
            email_verified=False,
        )

    def with_email(self, email: str) -> ProviderAccount | None:
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
        return ProviderAccount(
            AccountId(account["id"]),
            account["email"],
            frozenset(Role(role["name"]) for role in roles.json() if role["name"] in Role),
            email_verified=account["emailVerified"],
        )

    def send_email_verification(self, account_id: AccountId) -> None:
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
