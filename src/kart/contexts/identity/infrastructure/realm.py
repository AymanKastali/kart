"""The settings Identity keeps the kart realm at.

Keycloak imports the realm only when it doesn't exist yet, so a setting added later would never
reach an existing stack. Applying the settings through the admin API on every start does.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from kart.contexts.identity.contracts import Role
from kart.contexts.identity.infrastructure.keycloak import (
    SELLERS_GROUP,
    KeycloakAdminLogin,
    admin_client,
)

if TYPE_CHECKING:
    import httpx

_PASSWORD_POLICY = "length(8) and notUsername and notEmail"  # noqa: S105 a rule, not a password
# Keycloak's default profile asks every Account for these, but Kart never does: a Seller's
# names are in its Seller Application.
_OPTIONAL_PROFILE_ATTRIBUTES = {"firstName", "lastName"}


@dataclass(frozen=True, slots=True)
class SmtpLogin:
    username: str
    password: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class SmtpServer:
    """Where Keycloak sends its email from: Mailpit locally, Resend in production."""

    host: str
    port: int
    sender: str
    starttls: bool
    # Only a server that asks for a login gets one.
    login: SmtpLogin | None = None


def apply_realm_settings(admin: KeycloakAdminLogin, smtp_server: SmtpServer) -> None:
    """Give the realm its email, email verification, password reset and password policy, let
    an Account sign in with only an email and a password, and give it the group of Sellers.

    Applying the same settings again changes nothing.
    """
    with admin_client(admin) as admin_api:
        # The admin API's root is the realm itself.
        admin_api.put(
            "",
            json={
                "smtpServer": _smtp_settings(smtp_server),
                "verifyEmail": True,
                "resetPasswordAllowed": True,
                "passwordPolicy": _PASSWORD_POLICY,
            },
        ).raise_for_status()
        _make_names_optional(admin_api)
        _add_sellers_group(admin_api)


def _add_sellers_group(admin_api: httpx.Client) -> None:
    """The group whose members hold the `seller` role, unless the realm has it already."""
    groups = admin_api.get(
        "/groups", params={"search": SELLERS_GROUP, "exact": "true"}
    ).raise_for_status()
    if groups.json():
        return
    created = admin_api.post("/groups", json={"name": SELLERS_GROUP}).raise_for_status()
    seller_role = admin_api.get(f"/roles/{Role.SELLER}").raise_for_status().json()
    admin_api.post(
        f"{created.headers['Location']}/role-mappings/realm", json=[seller_role]
    ).raise_for_status()


def _make_names_optional(admin_api: httpx.Client) -> None:
    profile = admin_api.get("/users/profile").raise_for_status().json()
    for attribute in profile["attributes"]:
        if attribute["name"] in _OPTIONAL_PROFILE_ATTRIBUTES:
            attribute.pop("required", None)
    admin_api.put("/users/profile", json=profile).raise_for_status()


def _smtp_settings(server: SmtpServer) -> dict[str, str]:
    # Keycloak keeps every SMTP setting as a string.
    settings = {
        "host": server.host,
        "port": str(server.port),
        "from": server.sender,
        "fromDisplayName": "Kart",
        "starttls": _flag(server.starttls),
        "auth": _flag(server.login is not None),
    }
    if server.login is not None:
        settings |= {"user": server.login.username, "password": server.login.password}
    return settings


def _flag(value: bool) -> str:  # noqa: FBT001 a value, not an option
    return str(value).lower()
