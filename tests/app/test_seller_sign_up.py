"""A business signs up for a Seller Account through the API, against real Keycloak, Postgres and
Mailpit."""

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import make_url

from kart.app.api import create_app
from kart.app.migrate import migrate
from kart.contexts.identity.contracts import AccessTokens, Principal, Role
from kart.shared.kernel.ids import AccountId
from tests.app.environment import set_environment
from tests.app.keycloak import ADMIN, Credentials, KeycloakAdmin, access_token, email_address
from tests.app.keycloak_sign_in import verify_email
from tests.conftest import new_database
from tests.outbox_events import watching_outbox

if TYPE_CHECKING:
    from collections.abc import Iterator

    from testcontainers.community.postgres import PostgresContainer

    from tests.mailpit import Mailpit
    from tests.outbox_events import OutboxEvents

SIGN_UP = "/v1/storefront/seller-accounts"
PASSWORD = "a-good-password"  # noqa: S105 a throwaway Account's


@pytest.fixture(scope="module")
def database_url(postgres: PostgresContainer) -> str:
    url = new_database(postgres)
    migrate(url)
    return url


@pytest.fixture
def api(keycloak: str, database_url: str, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    url = make_url(database_url)
    set_environment(
        monkeypatch,
        KEYCLOAK_URL=keycloak,
        KC_BOOTSTRAP_ADMIN_USERNAME=ADMIN.username,
        KC_BOOTSTRAP_ADMIN_PASSWORD=ADMIN.password,
        POSTGRES_HOST=str(url.host),
        POSTGRES_PORT=str(url.port),
        POSTGRES_USER=str(url.username),
        POSTGRES_PASSWORD=str(url.password),
        POSTGRES_DB=str(url.database),
    )
    with TestClient(create_app()) as client:
        yield client


@pytest.fixture
def identity_outbox(database_url: str) -> Iterator[OutboxEvents]:
    with watching_outbox(database_url, "identity") as outbox:
        yield outbox


def new_email() -> str:
    return f"seller-{uuid4().hex}@example.com"


def test_signing_up_answers_with_the_new_account_id(api: TestClient) -> None:
    response = api.post(SIGN_UP, json={"email": new_email(), "password": PASSWORD})

    assert response.status_code == 201
    assert UUID(response.json()["account_id"])


def test_signing_up_emails_a_link_to_verify_the_address(api: TestClient, mailpit: Mailpit) -> None:
    email = new_email()

    api.post(SIGN_UP, json={"email": email, "password": PASSWORD})

    assert mailpit.email_to(email).subject == "Verify email"


def test_a_seller_cant_sign_in_before_verifying_their_email(keycloak: str, api: TestClient) -> None:
    email = new_email()
    api.post(SIGN_UP, json={"email": email, "password": PASSWORD})

    with pytest.raises(httpx.HTTPStatusError, match="400 Bad Request"):
        access_token(keycloak, Credentials(email, PASSWORD))


def test_a_verified_seller_signs_in_as_a_seller(
    keycloak: str, api: TestClient, mailpit: Mailpit
) -> None:
    email = new_email()
    response = api.post(SIGN_UP, json={"email": email, "password": PASSWORD})

    verify_email(mailpit.email_to(email))

    token = access_token(keycloak, Credentials(email, PASSWORD))
    account_id = AccountId(response.json()["account_id"])
    assert AccessTokens(keycloak).verify(token) == Principal(account_id, Role.SELLER)


def test_an_email_that_already_has_an_account_is_refused(api: TestClient) -> None:
    email = new_email()
    api.post(SIGN_UP, json={"email": email, "password": PASSWORD})

    response = api.post(SIGN_UP, json={"email": email, "password": PASSWORD})

    assert response.status_code == 409


def test_a_malformed_email_is_refused(api: TestClient) -> None:
    response = api.post(SIGN_UP, json={"email": "not-an-email", "password": PASSWORD})

    assert response.status_code == 422
    assert "not a valid email address" in response.text


def test_a_password_the_realm_refuses_is_refused_with_the_reason(api: TestClient) -> None:
    response = api.post(SIGN_UP, json={"email": new_email(), "password": "short"})

    assert response.status_code == 422
    assert response.json() == {"detail": "Invalid password: minimum length 8."}


def test_a_password_equal_to_the_email_is_refused(api: TestClient) -> None:
    email = new_email()

    response = api.post(SIGN_UP, json={"email": email, "password": email})

    assert response.status_code == 422
    assert response.json() == {"detail": "Invalid password: must not be equal to the username."}


def test_signing_up_publishes_that_an_account_registered(
    api: TestClient, identity_outbox: OutboxEvents
) -> None:
    email = new_email()

    response = api.post(SIGN_UP, json={"email": email, "password": PASSWORD})

    [event] = identity_outbox.published()
    assert event.type == "account.registered.v1"
    assert event.payload == {
        "account_id": response.json()["account_id"],
        "role": "seller",
        "email": email,
    }


def test_an_email_that_already_has_an_account_is_announced_only_once(
    api: TestClient, identity_outbox: OutboxEvents
) -> None:
    email = new_email()
    api.post(SIGN_UP, json={"email": email, "password": PASSWORD})

    api.post(SIGN_UP, json={"email": email, "password": PASSWORD})

    assert len(identity_outbox.published()) == 1


def test_a_retry_registers_a_seller_account_that_a_crash_left_unregistered(
    keycloak: str, api: TestClient, identity_outbox: OutboxEvents
) -> None:
    # Created in Keycloak, as by a sign-up that crashed before Identity recorded the Account.
    admin = KeycloakAdmin(keycloak)
    seller = email_address(admin.new_account([Role.SELLER]))

    response = api.post(SIGN_UP, json={"email": seller, "password": PASSWORD})

    assert response.status_code == 409
    [event] = identity_outbox.published()
    assert event.payload["email"] == seller
    assert event.payload["account_id"] == admin.account_id_with_email(seller)


def test_a_retry_makes_an_account_that_a_crash_left_without_a_role_a_seller(
    keycloak: str, api: TestClient, identity_outbox: OutboxEvents
) -> None:
    admin = KeycloakAdmin(keycloak)
    credentials = admin.new_account([])

    api.post(SIGN_UP, json={"email": email_address(credentials), "password": PASSWORD})

    principal = AccessTokens(keycloak).verify(access_token(keycloak, credentials))
    assert principal.role == Role.SELLER
    [event] = identity_outbox.published()
    assert event.payload["role"] == "seller"


def test_an_email_held_by_another_roles_account_is_refused_without_registering_it(
    keycloak: str, api: TestClient, identity_outbox: OutboxEvents
) -> None:
    customer = email_address(KeycloakAdmin(keycloak).new_account([Role.CUSTOMER]))

    response = api.post(SIGN_UP, json={"email": customer, "password": PASSWORD})

    assert response.status_code == 409
    assert identity_outbox.published() == []
