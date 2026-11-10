"""A Seller submits a Seller Application and reads it back through the API, against real Keycloak
and Postgres."""

from typing import TYPE_CHECKING
from uuid import UUID

import pytest

from kart.contexts.identity.contracts import Role
from tests.app.keycloak import KeycloakAdmin, access_token, bearer, local_account

if TYPE_CHECKING:
    from fastapi.testclient import TestClient

SELLER_APPLICATION = "/v1/seller/application"
BUSINESS_DETAILS = {
    "legal_name": "Falcon Trading LLC",
    "display_name": "Falcon",
    "trade_licence_number": "CN-1234567",
    "vat_number": "100123456700003",
    "iban": "AE070331234567890123456",
}


def signed_in_new_seller(keycloak: str) -> dict[str, str]:
    """The headers of a new Seller Account, which has submitted nothing yet."""
    seller = KeycloakAdmin(keycloak).new_account([Role.SELLER])
    return bearer(access_token(keycloak, seller))


def first_submission(business_details: dict[str, str]) -> dict:
    return {"business_details": business_details}


def correction(business_details: dict[str, str], *, version: int) -> dict:
    return {"business_details": business_details, "version": version}


def test_a_seller_application_is_not_found_before_it_is_submitted(
    keycloak: str, api: TestClient
) -> None:
    response = api.get(SELLER_APPLICATION, headers=signed_in_new_seller(keycloak))

    assert response.status_code == 404
    assert response.json() == {"detail": "This Seller has submitted no Seller Application"}


def test_the_first_submission_makes_a_pending_seller_application(
    keycloak: str, api: TestClient
) -> None:
    seller = signed_in_new_seller(keycloak)

    api.put(SELLER_APPLICATION, headers=seller, json=first_submission(BUSINESS_DETAILS))

    seller_application = api.get(SELLER_APPLICATION, headers=seller).json()
    assert UUID(seller_application["seller_id"])
    assert seller_application == {
        "seller_id": seller_application["seller_id"],
        "business_details": BUSINESS_DETAILS,
        "status": "pending",
        "version": 1,
    }


def test_correcting_a_pending_seller_application_keeps_it_pending_as_its_next_version(
    keycloak: str, api: TestClient
) -> None:
    seller = signed_in_new_seller(keycloak)
    first = api.put(SELLER_APPLICATION, headers=seller, json=first_submission(BUSINESS_DETAILS))
    corrected = BUSINESS_DETAILS | {"display_name": "Falcon Home"}

    api.put(SELLER_APPLICATION, headers=seller, json=correction(corrected, version=1))

    assert api.get(SELLER_APPLICATION, headers=seller).json() == {
        "seller_id": first.json()["seller_id"],
        "business_details": corrected,
        "status": "pending",
        "version": 2,
    }


def test_a_correction_with_the_same_details_changes_nothing(keycloak: str, api: TestClient) -> None:
    seller = signed_in_new_seller(keycloak)
    api.put(SELLER_APPLICATION, headers=seller, json=first_submission(BUSINESS_DETAILS))

    api.put(SELLER_APPLICATION, headers=seller, json=correction(BUSINESS_DETAILS, version=1))

    assert api.get(SELLER_APPLICATION, headers=seller).json()["version"] == 1


def test_a_correction_at_a_stale_version_is_refused(keycloak: str, api: TestClient) -> None:
    seller = signed_in_new_seller(keycloak)
    api.put(SELLER_APPLICATION, headers=seller, json=first_submission(BUSINESS_DETAILS))
    from_another_tab = BUSINESS_DETAILS | {"display_name": "Falcon Home"}
    api.put(SELLER_APPLICATION, headers=seller, json=correction(from_another_tab, version=1))

    response = api.put(
        SELLER_APPLICATION, headers=seller, json=correction(BUSINESS_DETAILS, version=1)
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "The Seller Application has changed since that version"}
    assert api.get(SELLER_APPLICATION, headers=seller).json()["business_details"] == (
        from_another_tab
    )


def test_a_second_first_submission_is_refused(keycloak: str, api: TestClient) -> None:
    seller = signed_in_new_seller(keycloak)
    api.put(SELLER_APPLICATION, headers=seller, json=first_submission(BUSINESS_DETAILS))

    response = api.put(
        SELLER_APPLICATION,
        headers=seller,
        json=first_submission(BUSINESS_DETAILS | {"display_name": "Falcon Home"}),
    )

    assert response.status_code == 409
    assert response.json() == {
        "detail": "This Seller has submitted a Seller Application already: correct it at the "
        "version it read"
    }


def test_correcting_a_seller_application_never_submitted_is_not_found(
    keycloak: str, api: TestClient
) -> None:
    response = api.put(
        SELLER_APPLICATION,
        headers=signed_in_new_seller(keycloak),
        json=correction(BUSINESS_DETAILS, version=1),
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "This Seller has submitted no Seller Application"}


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("legal_name", "   "),
        ("display_name", ""),
        ("trade_licence_number", " "),
        pytest.param("vat_number", "10012345670000", id="vat_number-14-digits"),
        pytest.param("vat_number", "1001234567000033", id="vat_number-16-digits"),
        pytest.param("vat_number", "10012345670000A", id="vat_number-a-letter"),
        pytest.param("iban", "GB82WEST12345698765432", id="iban-not-uae"),
        pytest.param("iban", "AE07033123456789012345", id="iban-too-short"),
        pytest.param("iban", "AE070331234567890123457", id="iban-bad-checksum"),
    ],
)
def test_an_invalid_business_detail_is_refused_naming_the_field(
    keycloak: str, api: TestClient, field: str, value: str
) -> None:
    response = api.put(
        SELLER_APPLICATION,
        headers=signed_in_new_seller(keycloak),
        json=first_submission(BUSINESS_DETAILS | {field: value}),
    )

    assert response.status_code == 422
    [refusal] = response.json()["detail"]
    assert refusal["loc"] == ["body", "business_details", field]


def test_names_and_the_trade_licence_number_are_kept_without_surrounding_spaces(
    keycloak: str, api: TestClient
) -> None:
    seller = signed_in_new_seller(keycloak)
    padded = {
        "legal_name": " Falcon Trading LLC ",
        "display_name": "  Falcon",
        "trade_licence_number": "CN-1234567  ",
    }

    api.put(SELLER_APPLICATION, headers=seller, json=first_submission(BUSINESS_DETAILS | padded))

    assert api.get(SELLER_APPLICATION, headers=seller).json()["business_details"] == (
        BUSINESS_DETAILS
    )


@pytest.mark.parametrize("role", [Role.CUSTOMER, Role.OPERATOR])
@pytest.mark.parametrize("method", ["GET", "PUT"])
def test_only_a_seller_reaches_its_seller_application(
    keycloak: str, api: TestClient, role: Role, method: str
) -> None:
    token = access_token(keycloak, local_account(role))

    response = api.request(
        method, SELLER_APPLICATION, headers=bearer(token), json=first_submission(BUSINESS_DETAILS)
    )

    assert response.status_code == 403
