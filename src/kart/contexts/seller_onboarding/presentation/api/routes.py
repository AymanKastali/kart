"""Seller Onboarding's HTTP routes: a Seller's own Seller Application."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import AfterValidator, BaseModel, StringConstraints

from kart.contexts.identity.contracts import Principal  # noqa: TC001 FastAPI reads it
from kart.contexts.identity.contracts.signed_in import signed_in_principal
from kart.contexts.seller_onboarding.application.seller_applications import (
    SellerApplications,  # noqa: TC001 FastAPI reads it
)
from kart.contexts.seller_onboarding.domain.seller_application import (
    BusinessDetails,
    Iban,
    NoSellerApplicationError,
    SellerApplication,
    SellerApplicationSubmittedError,
    Status,
    VatNumber,
    parse_iban,
    parse_vat_number,
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
    def from_business_details(cls, business_details: BusinessDetails) -> BusinessDetailsJson:
        return cls(
            legal_name=business_details.legal_name,
            display_name=business_details.display_name,
            trade_licence_number=business_details.trade_licence_number,
            vat_number=business_details.vat_number,
            iban=business_details.iban,
        )

    def to_business_details(self) -> BusinessDetails:
        return BusinessDetails(
            legal_name=self.legal_name,
            display_name=self.display_name,
            trade_licence_number=self.trade_licence_number,
            vat_number=self.vat_number,
            iban=self.iban,
        )


class SubmissionJson(BaseModel):
    business_details: BusinessDetailsJson


class SellerApplicationJson(BaseModel):
    seller_id: UUID
    business_details: BusinessDetailsJson
    status: Status

    @classmethod
    def from_seller_application(
        cls, seller_application: SellerApplication
    ) -> SellerApplicationJson:
        return cls(
            seller_id=seller_application.seller_id,
            business_details=BusinessDetailsJson.from_business_details(
                seller_application.business_details
            ),
            status=seller_application.status,
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
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "This Seller has submitted no Seller Application"
        ) from None
    return SellerApplicationJson.from_seller_application(seller_application)


@router.put(
    "",
    responses={status.HTTP_201_CREATED: {"description": "The first submission created it"}},
)
def submit_seller_application(
    submission: SubmissionJson,
    principal: Annotated[Principal, Depends(signed_in_principal)],
    applications: Annotated[SellerApplications, Depends(seller_applications)],
    *,
    response: Response,
) -> SellerApplicationJson:
    """Creates the Seller's Seller Application, or replaces its business details."""
    try:
        submitted = applications.submit(
            principal.account_id, submission.business_details.to_business_details()
        )
    except SellerApplicationSubmittedError:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Another submission created this Seller Application at the same time: submit again",
        ) from None
    if submitted.created:
        response.status_code = status.HTTP_201_CREATED
    return SellerApplicationJson.from_seller_application(submitted.seller_application)
