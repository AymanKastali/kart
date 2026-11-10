"""A Seller submits its Seller Application and reads it back."""

from typing import TYPE_CHECKING

from kart.contexts.seller_onboarding.infrastructure.seller_application_rows import (
    add,
    find,
    replace,
)
from kart.contexts.seller_onboarding.seller_application import (
    NoSellerApplicationError,
    first_submission,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from contextlib import AbstractContextManager

    from sqlalchemy.orm import Session

    from kart.contexts.seller_onboarding.seller_application import (
        BusinessDetails,
        SellerApplication,
    )
    from kart.shared.kernel.ids import AccountId

# One transaction in Seller Onboarding's schema, committed when the block succeeds.
type UnitOfWork = Callable[[], AbstractContextManager[Session]]


class SellerApplications:
    def __init__(self, unit_of_work: UnitOfWork) -> None:
        self._unit_of_work = unit_of_work

    def read(self, account_id: AccountId) -> SellerApplication:
        """The Seller Application of the Seller with this Account.

        Raises `NoSellerApplicationError` if it has submitted none.
        """
        with self._unit_of_work() as session:
            seller_application = find(session, account_id)
        if seller_application is None:
            raise NoSellerApplicationError
        return seller_application

    def submit(self, account_id: AccountId, details: BusinessDetails) -> SellerApplication:
        """The Seller Application with the business details the Seller submitted, for the first
        time or again.

        Raises `SellerApplicationChangedError` if another submission changed it meanwhile.
        """
        with self._unit_of_work() as session:
            current = find(session, account_id)
            if current is None:
                submitted = first_submission(account_id, details)
                add(session, submitted)
            else:
                submitted = current.resubmitted(details)
                replace(session, submitted, read_version=current.version)
        return submitted
