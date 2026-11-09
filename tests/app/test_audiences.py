"""Each audience prefix lets in only its role, checked with real tokens from a Keycloak that
loads the deployment's realm file."""

from contextlib import contextmanager
from typing import TYPE_CHECKING, Annotated

import pytest
from fastapi import APIRouter, Depends
from fastapi.testclient import TestClient

from kart.app.api import create_app
from kart.app.audiences import principal_for_audience
from kart.contexts.identity.contracts import Principal, Role
from tests.app.keycloak import (
    ADMIN,
    KeycloakAdmin,
    access_token,
    bearer,
    expired_token,
    local_account,
)
from tests.app.test_settings import ENVIRONMENT

if TYPE_CHECKING:
    from collections.abc import Callable, Generator

# Mounted under every audience prefix, standing in for the routes contexts will add.
throwaway_routes = APIRouter()


@throwaway_routes.get("")
@throwaway_routes.get("/whoami")
def whoami(
    principal: Annotated[Principal | None, Depends(principal_for_audience)],
) -> dict[str, str]:
    """What a route under an audience sees of the caller."""
    if principal is None:
        return {"role": "anonymous"}
    return {"account_id": str(principal.account_id), "role": principal.role}


@contextmanager
def running_api(identity_url: str, monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient]:
    """The real app, checking tokens with `identity_url`, plus the throwaway routes."""
    for name, value in {**ENVIRONMENT, "KEYCLOAK_URL": identity_url}.items():
        monkeypatch.setenv(name, value)
    app = create_app()
    for audience in ("storefront", *Role):
        app.include_router(throwaway_routes, prefix=f"/v1/{audience}")
    with TestClient(app) as client:
        yield client


@pytest.fixture
def api(keycloak: str, monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient]:
    with running_api(keycloak, monkeypatch) as client:
        yield client


@pytest.mark.parametrize("role", Role)
def test_each_role_reaches_its_own_audience(keycloak: str, api: TestClient, role: Role) -> None:
    token = access_token(keycloak, local_account(role))

    response = api.get(f"/v1/{role}/whoami", headers=bearer(token))

    assert response.status_code == 200
    assert response.json() == {
        "account_id": KeycloakAdmin(keycloak).account_id(role),
        "role": role,
    }


@pytest.mark.parametrize(
    ("role", "audience"),
    [(role, audience) for role in Role for audience in Role if role != audience],
)
def test_a_role_is_forbidden_other_audiences(
    keycloak: str, api: TestClient, role: Role, audience: Role
) -> None:
    token = access_token(keycloak, local_account(role))

    response = api.get(f"/v1/{audience}/whoami", headers=bearer(token))

    assert response.status_code == 403


@pytest.mark.parametrize("role", Role)
def test_the_storefront_is_open_to_every_role(keycloak: str, api: TestClient, role: Role) -> None:
    token = access_token(keycloak, local_account(role))

    response = api.get("/v1/storefront/whoami", headers=bearer(token))

    assert response.status_code == 200


def test_the_storefront_is_open_without_a_token(api: TestClient) -> None:
    response = api.get("/v1/storefront/whoami")

    assert response.status_code == 200
    assert response.json() == {"role": "anonymous"}


@pytest.mark.parametrize(
    "path", [f"/v1/{audience}{route}" for audience in Role for route in ("", "/whoami")]
)
def test_a_signed_in_audience_needs_a_token(api: TestClient, path: str) -> None:
    response = api.get(path)

    assert response.status_code == 401


@pytest.mark.parametrize(
    "token",
    [
        pytest.param(lambda _: "not-a-token", id="garbage"),
        pytest.param(expired_token, id="expired"),
        pytest.param(
            lambda keycloak: access_token(keycloak, ADMIN, realm="master", client_id="admin-cli"),
            id="another realm",
        ),
        pytest.param(
            lambda keycloak: access_token(keycloak, KeycloakAdmin(keycloak).new_account([])),
            id="no role",
        ),
        pytest.param(
            lambda keycloak: access_token(
                keycloak, KeycloakAdmin(keycloak).new_account(["customer", "seller"])
            ),
            id="two roles",
        ),
    ],
)
def test_an_invalid_token_is_refused(
    keycloak: str, api: TestClient, token: Callable[[str], str]
) -> None:
    response = api.get("/v1/customer/whoami", headers=bearer(token(keycloak)))

    assert response.status_code == 401


def test_a_token_cant_be_checked_while_keycloak_is_unreachable(
    keycloak: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    token = access_token(keycloak, local_account("customer"))

    # Nothing listens on port 1.
    with running_api("http://127.0.0.1:1", monkeypatch) as api:
        response = api.get("/v1/customer/whoami", headers=bearer(token))

    assert response.status_code == 503
