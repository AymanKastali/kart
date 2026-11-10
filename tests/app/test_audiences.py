"""Each audience prefix lets in only its role, checked with real tokens from a Keycloak that
loads the deployment's realm file."""

from contextlib import contextmanager
from typing import TYPE_CHECKING, Annotated

import pytest
from fastapi import APIRouter, Depends
from fastapi.testclient import TestClient

from kart.app.api import create_app
from kart.contexts.identity.contracts import Principal, Role
from kart.contexts.identity.contracts.signed_in import signed_in_principal
from tests.app.environment import set_environment
from tests.app.keycloak import (
    KeycloakAdmin,
    access_token,
    admin_token,
    bearer,
    expired_token,
    local_account,
    token_for_an_account_with_two_roles,
    token_for_an_account_without_a_role,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Generator

# Mounted under each signed-in audience's prefix, standing in for the routes contexts add.
signed_in_routes = APIRouter()
# Mounted under the storefront's.
open_routes = APIRouter()


@signed_in_routes.get("")
@signed_in_routes.get("/whoami")
def whoami(principal: Annotated[Principal, Depends(signed_in_principal)]) -> dict[str, str]:
    """What a route under a signed-in audience sees of the Principal."""
    return {"account_id": str(principal.account_id), "role": principal.role}


@open_routes.get("/anything")
def anything() -> dict[str, str]:
    return {}


@contextmanager
def running_api(keycloak: str, monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient]:
    """The real app, checking tokens with the Keycloak at `keycloak`, plus stand-in routes."""
    set_environment(monkeypatch, KEYCLOAK_URL=keycloak)
    app = create_app()
    for role in Role:
        app.include_router(signed_in_routes, prefix=f"/v1/{role}")
    app.include_router(open_routes, prefix="/v1/storefront")
    with TestClient(app) as client:
        yield client


@pytest.fixture
def api(keycloak: str, monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient]:
    with running_api(keycloak, monkeypatch) as client:
        yield client


@pytest.mark.parametrize("role", Role)
def test_each_role_reaches_its_own_audience(keycloak: str, api: TestClient, role: Role) -> None:
    token = access_token(keycloak, local_account(role))
    account_id = KeycloakAdmin(keycloak).account_id(role)

    response = api.get(f"/v1/{role}/whoami", headers=bearer(token))

    assert response.status_code == 200
    assert response.json() == {"account_id": account_id, "role": role}


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

    response = api.get("/v1/storefront/anything", headers=bearer(token))

    assert response.status_code == 200


def test_the_storefront_is_open_without_a_token(api: TestClient) -> None:
    response = api.get("/v1/storefront/anything")

    assert response.status_code == 200


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
        pytest.param(admin_token, id="another realm"),
        pytest.param(token_for_an_account_without_a_role, id="no role"),
        pytest.param(token_for_an_account_with_two_roles, id="two roles"),
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
    token = access_token(keycloak, local_account(Role.CUSTOMER))

    # Nothing listens on port 1.
    with running_api("http://127.0.0.1:1", monkeypatch) as api:
        response = api.get("/v1/customer/whoami", headers=bearer(token))

    assert response.status_code == 503
