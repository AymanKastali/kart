"""Tokens and Accounts from a test Keycloak, through its token endpoint and admin API."""

import time
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

import httpx

from kart.contexts.identity.contracts import Role
from kart.contexts.identity.keycloak import REALM, KeycloakAdminLogin
from kart.contexts.identity.realm import apply_realm_settings
from tests.mailpit import SMTP_SERVER

# The client the API accepts tokens for.
API_CLIENT_ID = "kart-api"


@dataclass(frozen=True, slots=True)
class Credentials:
    username: str
    password: str


ADMIN = Credentials("admin", "admin")


def local_account(role: Role) -> Credentials:
    """The realm's local Account for `role`: named after it, with that as its password too."""
    return Credentials(role, role)


def email_address(credentials: Credentials) -> str:
    """The email address of an Account made by `KeycloakAdmin.new_account`."""
    return f"{credentials.username}@example.com"


def access_token(
    keycloak: str,
    credentials: Credentials,
    *,
    realm: str = REALM,
    client_id: str = API_CLIENT_ID,
) -> str:
    response = httpx.post(
        f"{keycloak}/realms/{realm}/protocol/openid-connect/token",
        data={
            "grant_type": "password",
            "client_id": client_id,
            "username": credentials.username,
            "password": credentials.password,
        },
    )
    response.raise_for_status()
    return response.json()["access_token"]


def admin_token(keycloak: str) -> str:
    """A token for the bootstrap admin, from the master realm rather than kart's."""
    return access_token(keycloak, ADMIN, realm="master", client_id="admin-cli")


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def set_up_realm(keycloak: str) -> None:
    """Apply the kart realm's settings as Compose's setup does, sending email to Mailpit."""
    admin = KeycloakAdminLogin(keycloak, ADMIN.username, ADMIN.password)
    apply_realm_settings(admin, SMTP_SERVER)


class KeycloakAdmin:
    """Changes the kart realm through the admin API, as the bootstrap admin."""

    def __init__(self, keycloak: str) -> None:
        self._realm_url = f"{keycloak}/admin/realms/{REALM}"
        self._client = httpx.Client(headers=bearer(admin_token(keycloak)))

    def realm(self) -> dict:
        """The realm's settings, as the admin API represents them."""
        return self._get("")

    def account_id(self, username: str) -> str:
        return self._account_id(f"username={username}")

    def account_id_with_email(self, email: str) -> str:
        return self._account_id(f"email={email}")

    def new_account(self, roles: list[Role]) -> Credentials:
        """A new Account with exactly `roles`."""
        credentials = Credentials(f"account-{uuid4().hex}", "password")
        account = self._post("/users", _account(credentials))
        realm_roles = [self._get(f"/roles/{role}") for role in roles]
        self._client.post(
            f"{account.headers['Location']}/role-mappings/realm", json=realm_roles
        ).raise_for_status()
        return credentials

    def new_client_with_one_second_tokens(self) -> str:
        """The id of a new client whose tokens, also for the API, expire after a second."""
        client_id = f"short-lived-{uuid4().hex}"
        self._post(
            "/clients",
            {
                "clientId": client_id,
                "publicClient": True,
                "directAccessGrantsEnabled": True,
                "attributes": {"access.token.lifespan": "1"},
                "protocolMappers": [_api_audience_mapper()],
            },
        )
        return client_id

    def _account_id(self, search: str) -> str:
        [account] = self._get(f"/users?{search}&exact=true")
        return account["id"]

    def _get(self, path: str) -> Any:  # noqa: ANN401 whatever JSON the admin API answers with
        response = self._client.get(f"{self._realm_url}{path}")
        response.raise_for_status()
        return response.json()

    def _post(self, path: str, body: dict) -> httpx.Response:
        response = self._client.post(f"{self._realm_url}{path}", json=body)
        response.raise_for_status()
        return response


def expired_token(keycloak: str) -> str:
    """A token for the local customer that has already expired."""
    client_id = KeycloakAdmin(keycloak).new_client_with_one_second_tokens()
    token = access_token(keycloak, local_account(Role.CUSTOMER), client_id=client_id)
    time.sleep(2)
    return token


def token_for_an_account_without_a_role(keycloak: str) -> str:
    return access_token(keycloak, KeycloakAdmin(keycloak).new_account([]))


def token_for_an_account_with_two_roles(keycloak: str) -> str:
    account = KeycloakAdmin(keycloak).new_account([Role.CUSTOMER, Role.SELLER])
    return access_token(keycloak, account)


def _account(credentials: Credentials) -> dict:
    # Keycloak won't sign in an Account whose profile is incomplete.
    return {
        "username": credentials.username,
        "email": email_address(credentials),
        "firstName": "Test",
        "lastName": "Account",
        "enabled": True,
        "emailVerified": True,
        "credentials": [{"type": "password", "value": credentials.password, "temporary": False}],
    }


def _api_audience_mapper() -> dict:
    """Puts the API client in a token's audience, as the realm's own kart-api client does."""
    return {
        "name": "kart-api audience",
        "protocol": "openid-connect",
        "protocolMapper": "oidc-audience-mapper",
        "config": {"included.client.audience": API_CLIENT_ID, "access.token.claim": "true"},
    }
