"""A Seller submits its Seller Application, as often as it likes, and reads it back."""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from kart.contexts.seller_onboarding.domain.seller_application import (
    NoSellerApplicationError,
    SellerApplication,
    first_submission,
)

if TYPE_CHECKING:
    from kart.contexts.seller_onboarding.application.ports import SellerApplicationRepository
    from kart.contexts.seller_onboarding.domain.seller_application import BusinessDetails
    from kart.shared.kernel.ids import AccountId
    from kart.shared.kernel.unit_of_work import UnitOfWork


@dataclass(frozen=True, slots=True)
class Submission:
    seller_application: SellerApplication
    # Whether this submission created the Seller Application, rather than correcting it.
    created: bool


class SellerApplications:
    def __init__(self, unit_of_work: UnitOfWork[SellerApplicationRepository]) -> None:
        self._unit_of_work = unit_of_work

    def read(self, account_id: AccountId) -> SellerApplication:
        """The Seller Application of the Seller with this Account.

        Raises `NoSellerApplicationError` if it has submitted none.
        """
        with self._unit_of_work() as repository:
            seller_application = repository.find(account_id)
        if seller_application is None:
            raise NoSellerApplicationError
        return seller_application

    def submit(self, account_id: AccountId, business_details: BusinessDetails) -> Submission:
        """The Seller Application with these business details: created by the Seller's first
        submission, corrected by each one after it.

        Raises `SellerApplicationSubmittedError` if another first submission from the Seller
        created it at the same time.
        """
        with self._unit_of_work() as repository:
            current = repository.find(account_id)
            if current is None:
                submitted = first_submission(account_id, business_details)
                repository.add(submitted)
                return Submission(submitted, created=True)
            corrected = current.corrected(business_details)
            repository.replace(corrected)
            return Submission(corrected, created=False)
