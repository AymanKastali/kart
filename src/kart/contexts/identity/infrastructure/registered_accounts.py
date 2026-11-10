"""The Accounts Identity has registered, in its own schema, and the `account.registered.v1`
event that tells other contexts about each one (ADR-0005)."""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import Column, MetaData, String, Table, Uuid
from sqlalchemy.dialects.postgresql import insert

from kart.shared.kernel.event_envelope import EventEnvelope
from kart.shared.outbox import write_to_outbox

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from kart.contexts.identity.contracts import Role
    from kart.shared.kernel.ids import AccountId

_accounts = Table(
    "accounts",
    MetaData(),
    Column("account_id", Uuid, primary_key=True),
    Column("role", String, nullable=False),
    Column("email", String, nullable=False),
)


@dataclass(frozen=True, slots=True)
class Account:
    account_id: AccountId
    role: Role
    email: str


def register(session: Session, account: Account) -> None:
    """Record the Account and publish `account.registered.v1`, unless it is recorded already."""
    recorded = session.scalar(
        insert(_accounts)
        .values(account_id=account.account_id, role=account.role, email=account.email)
        .on_conflict_do_nothing()
        .returning(_accounts.c.account_id)
    )
    if recorded is not None:
        write_to_outbox(
            session, _registered(account), aggregate_type="account", aggregate_id=account.account_id
        )


def _registered(account: Account) -> EventEnvelope:
    return EventEnvelope(
        event_id=uuid4(),
        type="account.registered.v1",
        occurred_at=datetime.now(UTC),
        payload={
            "account_id": str(account.account_id),
            "role": account.role,
            "email": account.email,
        },
    )
