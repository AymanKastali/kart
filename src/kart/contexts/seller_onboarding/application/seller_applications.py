"""A Seller submits its Seller Application, corrects it and reads it back."""

from typing import TYPE_CHECKING

from kart.contexts.seller_onboarding.domain.seller_application import (
    NoSellerApplicationError,
    first_submission,
)

if TYPE_CHECKING:
    from kart.contexts.seller_onboarding.application.ports import SellerApplicationRepository
    from kart.contexts.seller_onboarding.domain.seller_application import (
        BusinessDetails,
        SellerApplication,
        Version,
    )
    from kart.shared.kernel.ids import AccountId
    from kart.shared.kernel.unit_of_work import UnitOfWork


class SellerApplications:
    def __init__(self, unit_of_work: UnitOfWork[SellerApplicationRepository]) -> None:
        self._unit_of_work = unit_of_work

    def read(self, account_id: AccountId) -> SellerApplication:
        """The Seller Application of the Seller with this Account.

        Raises `NoSellerApplicationError` if it has submitted none.
        """
        with self._unit_of_work() as repository:
            return _submitted(repository, account_id)

    def submit(self, account_id: AccountId, business_details: BusinessDetails) -> SellerApplication:
        """The Seller Application the Seller submitted for the first time.

        Raises `SellerApplicationSubmittedError` if it has submitted one already.
        """
        submitted = first_submission(account_id, business_details)
        with self._unit_of_work() as repository:
            repository.add(submitted)
        return submitted

    def correct(
        self, account_id: AccountId, business_details: BusinessDetails, *, read_version: Version
    ) -> SellerApplication:
        """The Seller Application with the business details the Seller corrected at the version it
        read.

        Raises `NoSellerApplicationError` if it has submitted none, and
        `SellerApplicationChangedError` if it has changed since `read_version`.
        """
        with self._unit_of_work() as repository:
            current = _submitted(repository, account_id)
            corrected = current.corrected(business_details, read_version=read_version)
            repository.replace(corrected, read_version=current.version)
        return corrected


def _submitted(repository: SellerApplicationRepository, account_id: AccountId) -> SellerApplication:
    seller_application = repository.find(account_id)
    if seller_application is None:
        raise NoSellerApplicationError
    return seller_application
