"""The Keycloak realm that holds Kart's Accounts, and its admin API, through which Identity
changes the realm and creates Accounts in it (ADR-0005)."""

from dataclasses import dataclass, field

import httpx

REALM = "kart"


@dataclass(frozen=True, slots=True)
class KeycloakAdminLogin:
    """Where Keycloak is, and how its administrator, who may change its realms, signs in."""

    url: str
    username: str
    password: str = field(repr=False)


def admin_client(admin: KeycloakAdminLogin) -> httpx.Client:
    """A client for the kart realm's admin API, signed in as Keycloak's administrator.

    Paths are relative to the realm, so `/users` is the realm's Accounts.
    """
    return httpx.Client(
        base_url=f"{admin.url}/admin/realms/{REALM}",
        headers={"Authorization": f"Bearer {_admin_token(admin)}"},
    )


def _admin_token(admin: KeycloakAdminLogin) -> str:
    response = httpx.post(
        f"{admin.url}/realms/master/protocol/openid-connect/token",
        data={
            "grant_type": "password",
            "client_id": "admin-cli",
            "username": admin.username,
            "password": admin.password,
        },
    )
    response.raise_for_status()
    return response.json()["access_token"]
