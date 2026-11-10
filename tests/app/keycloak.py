"""Tokens and accounts from a test Keycloak, through its token endpoint and admin API."""

import html
import re
import time
from dataclasses import dataclass
from uuid import uuid4

import httpx

from kart.contexts.identity.realm import REALM, KeycloakAdminLogin, apply_realm_settings
from tests.mailpit import SMTP_SERVER

# The client the API accepts tokens for.
API_CLIENT_ID = "kart-api"


@dataclass(frozen=True, slots=True)
class Login:
    username: str
    password: str


ADMIN = Login("admin", "admin")


def local_account(role: str) -> Login:
    """The realm's local account for `role`: named after it, with that as its password too."""
    return Login(role, role)


def access_token(
    keycloak: str, login: Login, *, realm: str = REALM, client_id: str = API_CLIENT_ID
) -> str:
    response = httpx.post(
        f"{keycloak}/realms/{realm}/protocol/openid-connect/token",
        data={
            "grant_type": "password",
            "client_id": client_id,
            "username": login.username,
            "password": login.password,
        },
    )
    response.raise_for_status()
    return response.json()["access_token"]


def set_up_realm(keycloak: str) -> None:
    """Apply the kart realm's settings as Compose's setup does, sending email to Mailpit."""
    admin = KeycloakAdminLogin(keycloak, ADMIN.username, ADMIN.password)
    apply_realm_settings(admin, SMTP_SERVER)


def request_password_reset(keycloak: str, username: str) -> None:
    """Ask for a reset link as a person does: through "Forgot password?" on the sign-in page."""
    with httpx.Client(follow_redirects=True) as browser:
        sign_in_page = browser.get(
            f"{keycloak}/realms/{REALM}/protocol/openid-connect/auth",
            params={
                # The realm's own account console: a client whose sign-in page is hosted.
                "client_id": "account-console",
                "redirect_uri": f"{keycloak}/realms/{REALM}/account/",
                "response_type": "code",
                "code_challenge": "a" * 43,
                "code_challenge_method": "S256",
            },
        )
        sign_in_page.raise_for_status()
        # Keycloak marks its session cookies Secure, which a browser sends to localhost over
        # plain http but httpx doesn't, so they are passed on by hand.
        session = {"Cookie": "; ".join(f"{n}={v}" for n, v in sign_in_page.cookies.items())}
        reset_page = browser.get(
            sign_in_page.url.join(_reset_link(sign_in_page.text)), headers=session
        )
        reset_page.raise_for_status()
        browser.post(
            reset_page.url.join(_form_action(reset_page.text)),
            data={"username": username},
            headers=session,
        ).raise_for_status()


def _reset_link(page: str) -> str:
    match = re.search(r'href="([^"]*/login-actions/reset-credentials[^"]*)"', page)
    if match is None:
        msg = "the sign-in page offers no password reset"
        raise AssertionError(msg)
    return html.unescape(match[1])


def _form_action(page: str) -> str:
    match = re.search(r'<form[^>]*action="([^"]*)"', page)
    if match is None:
        msg = "the page has no form"
        raise AssertionError(msg)
    return html.unescape(match[1])


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


class KeycloakAdmin:
    """Changes the kart realm through the admin API, as the bootstrap admin."""

    def __init__(self, keycloak: str) -> None:
        self._realm_url = f"{keycloak}/admin/realms/{REALM}"
        admin_token = access_token(keycloak, ADMIN, realm="master", client_id="admin-cli")
        self._client = httpx.Client(headers=bearer(admin_token))

    def realm(self) -> dict:
        """The realm's settings, as the admin API represents them."""
        response = self._client.get(self._realm_url)
        response.raise_for_status()
        return response.json()

    def account_id(self, username: str) -> str:
        users = self._get(f"/users?username={username}&exact=true")
        return users[0]["id"]

    def new_account(self, roles: list[str]) -> Login:
        """A new account with exactly `roles`."""
        login = Login(f"account-{uuid4().hex}", "password")
        account = self._post("/users", _account(login))
        realm_roles = [self._get(f"/roles/{role}") for role in roles]
        self._client.post(
            f"{account.headers['Location']}/role-mappings/realm", json=realm_roles
        ).raise_for_status()
        return login

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

    def _get(self, path: str) -> dict | list:
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
    token = access_token(keycloak, local_account("customer"), client_id=client_id)
    time.sleep(2)
    return token


def _account(login: Login) -> dict:
    # Keycloak won't sign in an account whose profile is incomplete.
    return {
        "username": login.username,
        "email": f"{login.username}@kart.local",
        "firstName": "Test",
        "lastName": "Account",
        "enabled": True,
        "emailVerified": True,
        "credentials": [{"type": "password", "value": login.password, "temporary": False}],
    }


def _api_audience_mapper() -> dict:
    """Puts the API client in a token's audience, as the realm's own kart-api client does."""
    return {
        "name": "kart-api audience",
        "protocol": "openid-connect",
        "protocolMapper": "oidc-audience-mapper",
        "config": {"included.client.audience": API_CLIENT_ID, "access.token.claim": "true"},
    }
