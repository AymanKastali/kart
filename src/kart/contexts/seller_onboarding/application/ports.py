"""What Seller Onboarding's use cases need from outside the process. The app hands each one an
adapter that implements it."""

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from kart.contexts.seller_onboarding.domain.seller_application import SellerApplication
    from kart.shared.kernel.ids import AccountId


class SellerApplicationRepository(Protocol):
    """Every Seller's one Seller Application, inside a Unit of Work."""

    def find(self, account_id: AccountId) -> SellerApplication | None:
        """The Seller Application the Seller with this Account submitted, if it submitted one."""
        ...

    def add(self, seller_application: SellerApplication) -> None:
        """Raises `SellerApplicationSubmittedError` if the Seller has one already."""
        ...

    def replace(self, seller_application: SellerApplication) -> None:
        """Replace the Seller's Seller Application with this one."""
        ...
