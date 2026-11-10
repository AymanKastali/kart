"""Seller Onboarding's HTTP routes: a Seller's own Seller Application."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import AfterValidator, BaseModel, StringConstraints

from kart.contexts.identity.contracts import Principal, signed_in_principal
from kart.contexts.seller_onboarding.seller_application import (
    BusinessDetails,
    Iban,
    NoSellerApplicationError,
    SellerApplication,
    SellerApplicationChangedError,
    Status,
    VatNumber,
    parse_iban,
    parse_vat_number,
)
from kart.contexts.seller_onboarding.seller_applications import (
    SellerApplications,  # noqa: TC001 FastAPI reads it
)

router = APIRouter(prefix="/v1/seller/application", tags=["Seller Onboarding"])

TrimmedText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class BusinessDetailsJson(BaseModel):
    legal_name: TrimmedText
    display_name: TrimmedText
    trade_licence_number: TrimmedText
    vat_number: Annotated[VatNumber, AfterValidator(parse_vat_number)]
    iban: Annotated[Iban, AfterValidator(parse_iban)]

    @classmethod
    def from_business_details(cls, details: BusinessDetails) -> BusinessDetailsJson:
        return cls(
            legal_name=details.legal_name,
            display_name=details.display_name,
            trade_licence_number=details.trade_licence_number,
            vat_number=details.vat_number,
            iban=details.iban,
        )

    def business_details(self) -> BusinessDetails:
        return BusinessDetails(
            legal_name=self.legal_name,
            display_name=self.display_name,
            trade_licence_number=self.trade_licence_number,
            vat_number=self.vat_number,
            iban=self.iban,
        )


class SubmissionJson(BaseModel):
    business_details: BusinessDetailsJson
    # The version of the Seller Application the Seller read and corrects; left out the first time.
    version: int | None = None


class SellerApplicationJson(BaseModel):
    seller_id: UUID
    business_details: BusinessDetailsJson
    status: Status
    version: int

    @classmethod
    def from_seller_application(
        cls, seller_application: SellerApplication
    ) -> SellerApplicationJson:
        return cls(
            seller_id=seller_application.seller_id,
            business_details=BusinessDetailsJson.from_business_details(seller_application.details),
            status=seller_application.status,
            version=seller_application.version,
        )


def seller_applications(request: Request) -> SellerApplications:
    """The app sets it up at startup, with what it reads from the environment."""
    return request.app.state.seller_applications


@router.get("")
def read_seller_application(
    principal: Annotated[Principal, Depends(signed_in_principal)],
    applications: Annotated[SellerApplications, Depends(seller_applications)],
) -> SellerApplicationJson:
    try:
        seller_application = applications.read(principal.account_id)
    except NoSellerApplicationError:
        raise _no_seller_application() from None
    return SellerApplicationJson.from_seller_application(seller_application)


@router.put("")
def submit_seller_application(
    submission: SubmissionJson,
    principal: Annotated[Principal, Depends(signed_in_principal)],
    applications: Annotated[SellerApplications, Depends(seller_applications)],
) -> SellerApplicationJson:
    details = submission.business_details.business_details()
    if submission.version is None:
        seller_application = _first_submission(applications, principal, details)
    else:
        seller_application = _correction(
            applications, principal, details, read_version=submission.version
        )
    return SellerApplicationJson.from_seller_application(seller_application)


def _first_submission(
    applications: SellerApplications, principal: Principal, details: BusinessDetails
) -> SellerApplication:
    try:
        return applications.submit(principal.account_id, details)
    except SellerApplicationChangedError:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "This Seller has submitted a Seller Application already: correct it at the version it "
            "read",
        ) from None


def _correction(
    applications: SellerApplications,
    principal: Principal,
    details: BusinessDetails,
    *,
    read_version: int,
) -> SellerApplication:
    try:
        return applications.correct(principal.account_id, details, read_version=read_version)
    except NoSellerApplicationError:
        raise _no_seller_application() from None
    except SellerApplicationChangedError:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "The Seller Application has changed since that version"
        ) from None


def _no_seller_application() -> HTTPException:
    return HTTPException(
        status.HTTP_404_NOT_FOUND, "This Seller has submitted no Seller Application"
    )
