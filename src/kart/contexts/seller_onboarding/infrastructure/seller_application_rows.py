"""Seller Applications, as rows in Seller Onboarding's schema."""

from typing import TYPE_CHECKING

from sqlalchemy import Column, Integer, MetaData, String, Table, Uuid, select, update
from sqlalchemy.dialects.postgresql import insert

from kart.contexts.seller_onboarding.seller_application import (
    BusinessDetails,
    Iban,
    SellerApplication,
    SellerApplicationChangedError,
    Status,
    VatNumber,
)
from kart.shared.kernel.ids import AccountId, SellerId

if TYPE_CHECKING:
    from sqlalchemy import Row
    from sqlalchemy.orm import Session

_seller_applications = Table(
    "seller_applications",
    MetaData(),
    Column("account_id", Uuid, primary_key=True),
    Column("seller_id", Uuid, nullable=False, unique=True),
    Column("legal_name", String, nullable=False),
    Column("display_name", String, nullable=False),
    Column("trade_licence_number", String, nullable=False),
    Column("vat_number", String, nullable=False),
    Column("iban", String, nullable=False),
    Column("status", String, nullable=False),
    Column("version", Integer, nullable=False),
)


def find(session: Session, account_id: AccountId) -> SellerApplication | None:
    """The Seller Application the Seller with this Account submitted, if it submitted one."""
    row = session.execute(
        select(_seller_applications).where(_seller_applications.c.account_id == account_id)
    ).one_or_none()
    return None if row is None else _seller_application(row)


def add(session: Session, seller_application: SellerApplication) -> None:
    """Raises `SellerApplicationChangedError` if the Seller has one already."""
    added = session.scalar(
        insert(_seller_applications)
        .values(_row(seller_application))
        .on_conflict_do_nothing(index_elements=[_seller_applications.c.account_id])
        .returning(_seller_applications.c.account_id)
    )
    if added is None:
        raise SellerApplicationChangedError


def replace(session: Session, seller_application: SellerApplication, *, read_version: int) -> None:
    """Replace the Seller Application as it was read at `read_version`.

    Raises `SellerApplicationChangedError` if another write has changed it since.
    """
    replaced = session.scalar(
        update(_seller_applications)
        .where(
            _seller_applications.c.account_id == seller_application.account_id,
            _seller_applications.c.version == read_version,
        )
        .values(_row(seller_application))
        .returning(_seller_applications.c.account_id)
    )
    if replaced is None:
        raise SellerApplicationChangedError


def _row(seller_application: SellerApplication) -> dict:
    details = seller_application.details
    return {
        "account_id": seller_application.account_id,
        "seller_id": seller_application.seller_id,
        "legal_name": details.legal_name,
        "display_name": details.display_name,
        "trade_licence_number": details.trade_licence_number,
        "vat_number": details.vat_number,
        "iban": details.iban,
        "status": seller_application.status,
        "version": seller_application.version,
    }


def _seller_application(row: Row) -> SellerApplication:
    return SellerApplication(
        account_id=AccountId(int=row.account_id.int),
        seller_id=SellerId(int=row.seller_id.int),
        details=BusinessDetails(
            legal_name=row.legal_name,
            display_name=row.display_name,
            trade_licence_number=row.trade_licence_number,
            vat_number=VatNumber(row.vat_number),
            iban=Iban(row.iban),
        ),
        status=Status(row.status),
        version=row.version,
    )
