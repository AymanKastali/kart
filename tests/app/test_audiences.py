"""Each audience prefix lets in only its role, checked with real tokens from a Keycloak that
loads the deployment's realm file."""

import time
from pathlib import Path
from typing import TYPE_CHECKING, Annotated
from uuid import uuid4

import httpx
import pytest
from fastapi import APIRouter, Depends
from fastapi.testclient import TestClient
from testcontainers.core.container import DockerContainer
from testcontainers.core.wait_strategies import LogMessageWaitStrategy

from kart.app.api import create_app
from kart.app.audiences import principal_for_audience
from kart.contexts.identity.contracts import Principal  # noqa: TC001 (FastAPI reads it at runtime)
from tests.app.test_settings import ENVIRONMENT

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

# tests/app/<this file> -> the repository root.
REALM_FILE = Path(__file__).resolve().parents[2] / "deploy/keycloak/kart-realm.json"
ADMIN = {"username": "admin", "password": "admin"}
ROLES = ["customer", "seller", "operator"]


@pytest.fixture(scope="session")
def keycloak() -> Iterator[str]:
    """The URL of a Keycloak that has imported the deployment's realm."""
    container = (
        DockerContainer("quay.io/keycloak/keycloak:26.4")
        .with_command("start-dev --import-realm")
        .with_env("KC_BOOTSTRAP_ADMIN_USERNAME", ADMIN["username"])
        .with_env("KC_BOOTSTRAP_ADMIN_PASSWORD", ADMIN["password"])
        .with_volume_mapping(str(REALM_FILE), "/opt/keycloak/data/import/kart-realm.json")
        .with_exposed_ports(8080)
        .waiting_for(LogMessageWaitStrategy("started in").with_startup_timeout(120))
    )
    with container:
        yield f"http://{container.get_container_host_ip()}:{container.get_exposed_port(8080)}"


# Mounted under every audience prefix, standing in for the routes contexts will add.
throwaway_routes = APIRouter()


@throwaway_routes.get("/whoami")
def whoami(
    principal: Annotated[Principal | None, Depends(principal_for_audience)],
) -> dict[str, str]:
    """What a route under an audience sees of the caller."""
    if principal is None:
        return {"role": "anonymous"}
    return {"account_id": str(principal.account_id), "role": principal.role}


@pytest.fixture
def api(keycloak: str, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """The real app, with a throwaway `whoami` route under every audience prefix."""
    for name, value in {**ENVIRONMENT, "KEYCLOAK_URL": keycloak}.items():
        monkeypatch.setenv(name, value)
    app = create_app()
    for audience in ("storefront", *ROLES):
        app.include_router(throwaway_routes, prefix=f"/v1/{audience}")
    with TestClient(app) as client:
        yield client


def access_token(keycloak: str, username: str, password: str, client_id: str = "kart-api") -> str:
    response = httpx.post(
        f"{keycloak}/realms/kart/protocol/openid-connect/token",
        data={
            "grant_type": "password",
            "client_id": client_id,
            "username": username,
            "password": password,
        },
    )
    response.raise_for_status()
    return response.json()["access_token"]


def account_id(keycloak: str, username: str) -> str:
    """The id Keycloak gave the account, read through its admin API."""
    response = httpx.get(
        f"{keycloak}/admin/realms/kart/users",
        params={"username": username, "exact": "true"},
        headers=_admin_headers(keycloak),
    )
    response.raise_for_status()
    return response.json()[0]["id"]


def _admin_headers(keycloak: str) -> dict[str, str]:
    response = httpx.post(
        f"{keycloak}/realms/master/protocol/openid-connect/token",
        data={"grant_type": "password", "client_id": "admin-cli", **ADMIN},
    )
    response.raise_for_status()
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.parametrize("role", ROLES)
def test_each_role_reaches_its_own_audience(keycloak: str, api: TestClient, role: str) -> None:
    # The local test accounts are named after their role, with that as their password too.
    token = access_token(keycloak, role, role)

    response = api.get(f"/v1/{role}/whoami", headers=bearer(token))

    assert response.status_code == 200
    assert response.json() == {"account_id": account_id(keycloak, role), "role": role}


@pytest.mark.parametrize(
    ("role", "audience"),
    [(role, audience) for role in ROLES for audience in ROLES if role != audience],
)
def test_a_role_is_forbidden_other_audiences(
    keycloak: str, api: TestClient, role: str, audience: str
) -> None:
    token = access_token(keycloak, role, role)

    response = api.get(f"/v1/{audience}/whoami", headers=bearer(token))

    assert response.status_code == 403


@pytest.mark.parametrize("role", ROLES)
def test_the_storefront_is_open_to_every_role(keycloak: str, api: TestClient, role: str) -> None:
    token = access_token(keycloak, role, role)

    response = api.get("/v1/storefront/whoami", headers=bearer(token))

    assert response.status_code == 200


def test_the_storefront_is_open_without_a_token(api: TestClient) -> None:
    response = api.get("/v1/storefront/whoami")

    assert response.status_code == 200
    assert response.json() == {"role": "anonymous"}


def new_account_token(keycloak: str, roles: list[str]) -> str:
    """A token for a new account that has exactly `roles`."""
    username = f"account-{uuid4().hex}"
    admin = _admin_headers(keycloak)
    response = httpx.post(
        f"{keycloak}/admin/realms/kart/users",
        headers=admin,
        json={
            "username": username,
            "email": f"{username}@kart.local",
            "firstName": "Test",
            "lastName": "Account",
            "enabled": True,
            "emailVerified": True,
            "credentials": [{"type": "password", "value": username, "temporary": False}],
        },
    )
    response.raise_for_status()
    user_url = response.headers["Location"]
    role_representations = [
        httpx.get(f"{keycloak}/admin/realms/kart/roles/{role}", headers=admin).json()
        for role in roles
    ]
    httpx.post(
        f"{user_url}/role-mappings/realm", headers=admin, json=role_representations
    ).raise_for_status()
    return access_token(keycloak, username, username)


def expired_token(keycloak: str) -> str:
    """A customer token that has already expired, from a client whose tokens last a second."""
    client_id = f"short-lived-{uuid4().hex}"
    httpx.post(
        f"{keycloak}/admin/realms/kart/clients",
        headers=_admin_headers(keycloak),
        json={
            "clientId": client_id,
            "publicClient": True,
            "directAccessGrantsEnabled": True,
            "attributes": {"access.token.lifespan": "1"},
            "protocolMappers": [
                {
                    "name": "kart-api audience",
                    "protocol": "openid-connect",
                    "protocolMapper": "oidc-audience-mapper",
                    "config": {
                        "included.client.audience": "kart-api",
                        "access.token.claim": "true",
                    },
                }
            ],
        },
    ).raise_for_status()
    token = access_token(keycloak, "customer", "customer", client_id)
    time.sleep(2)
    return token


@pytest.mark.parametrize("audience", ROLES)
def test_a_signed_in_audience_needs_a_token(api: TestClient, audience: str) -> None:
    response = api.get(f"/v1/{audience}/whoami")

    assert response.status_code == 401


@pytest.mark.parametrize(
    "token",
    [
        pytest.param(lambda _: "not-a-token", id="garbage"),
        pytest.param(expired_token, id="expired"),
        pytest.param(
            lambda keycloak: _admin_headers(keycloak)["Authorization"][7:], id="another realm"
        ),
        pytest.param(lambda keycloak: new_account_token(keycloak, []), id="no role"),
        pytest.param(
            lambda keycloak: new_account_token(keycloak, ["customer", "seller"]), id="two roles"
        ),
    ],
)
def test_an_invalid_token_is_refused(
    keycloak: str, api: TestClient, token: Callable[[str], str]
) -> None:
    response = api.get("/v1/customer/whoami", headers=bearer(token(keycloak)))

    assert response.status_code == 401
