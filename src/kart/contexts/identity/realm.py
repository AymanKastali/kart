"""The Keycloak realm that holds Kart's Accounts, and the settings Identity keeps it at.

Keycloak imports the realm only when it doesn't exist yet, so a setting added later would never
reach an existing stack. Applying the settings through the admin API on every start does.
"""

from dataclasses import dataclass, field

import httpx

REALM = "kart"
_PASSWORD_POLICY = "length(8) and notUsername and notEmail"  # noqa: S105 a rule, not a password


@dataclass(frozen=True, slots=True)
class KeycloakAdminLogin:
    """Where Keycloak is, and how its administrator, who may change its realms, signs in."""

    url: str
    username: str
    password: str = field(repr=False)


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
    """Give the realm its email, email verification, password reset and password policy.

    Applying the same settings again changes nothing.
    """
    response = httpx.put(
        f"{admin.url}/admin/realms/{REALM}",
        headers={"Authorization": f"Bearer {_admin_token(admin)}"},
        json={
            "smtpServer": _smtp_settings(smtp_server),
            "verifyEmail": True,
            "resetPasswordAllowed": True,
            "passwordPolicy": _PASSWORD_POLICY,
        },
    )
    response.raise_for_status()


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
