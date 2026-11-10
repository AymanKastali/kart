"""Identity's HTTP routes. Signing in, verifying an email and resetting a password are
Keycloak's own pages, so the only route is signing up."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr

from kart.contexts.identity.application.ports import EmailTakenError, SignUpRefusedError
from kart.contexts.identity.application.seller_sign_up import (
    SellerSignUp,  # noqa: TC001 FastAPI reads it
)
from kart.contexts.identity.domain.account import Credentials

router = APIRouter(prefix="/v1/storefront/seller-accounts", tags=["Identity"])


class SellerSignUpForm(BaseModel):
    email: EmailStr
    password: str


class SignedUpSeller(BaseModel):
    account_id: UUID


def seller_sign_up(request: Request) -> SellerSignUp:
    """The app sets it up at startup, with what it reads from the environment."""
    return request.app.state.seller_sign_up


@router.post("", status_code=status.HTTP_201_CREATED)
def sign_up_seller(
    form: SellerSignUpForm, sign_up: Annotated[SellerSignUp, Depends(seller_sign_up)]
) -> SignedUpSeller:
    try:
        account_id = sign_up.sign_up(Credentials(form.email, form.password))
    except EmailTakenError:
        raise HTTPException(status.HTTP_409_CONFLICT, "An Account already has this email") from None
    except SignUpRefusedError as refusal:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(refusal)) from None
    return SignedUpSeller(account_id=account_id)
