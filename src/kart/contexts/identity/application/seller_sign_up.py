"""A business signs up for a Seller Account."""

from typing import TYPE_CHECKING

from kart.contexts.identity.application.ports import EmailTakenError
from kart.contexts.identity.contracts import Role
from kart.contexts.identity.domain.account import Account

if TYPE_CHECKING:
    from kart.contexts.identity.application.ports import (
        AccountRepository,
        IdentityProvider,
        ProviderAccount,
    )
    from kart.contexts.identity.domain.account import Credentials
    from kart.shared.kernel.ids import AccountId
    from kart.shared.kernel.unit_of_work import UnitOfWork


class SellerSignUp:
    def __init__(
        self,
        identity_provider: IdentityProvider,
        unit_of_work: UnitOfWork[AccountRepository],
    ) -> None:
        self._identity_provider = identity_provider
        self._unit_of_work = unit_of_work

    def sign_up(self, credentials: Credentials) -> AccountId:
        """A new Seller Account, which signs in once it has verified its email.

        Raises `EmailTakenError` if an Account has the email, and `SignUpRefusedError` if the
        identity provider refuses the Account, such as for a password its policy refuses.
        """
        try:
            account = self._identity_provider.create_seller(credentials)
        except EmailTakenError:
            self._finish_a_sign_up_that_stopped_part_way(credentials.email)
            raise
        self._register_seller(account)
        self._identity_provider.send_email_verification(account.account_id)
        return account.account_id

    def _finish_a_sign_up_that_stopped_part_way(self, email: str) -> None:
        """Let a retry repair a sign-up that stopped after the identity provider created the
        Seller Account, such as in a crash before Identity registered it, or when its
        verification email couldn't be sent.

        Registering an Account again changes nothing, and the link is emailed again until the
        Account has verified its email. Any other Account with the email is left as it is.
        """
        account = self._identity_provider.with_email(email)
        if account is None or account.roles != {Role.SELLER}:
            return
        self._register_seller(account)
        if not account.email_verified:
            self._identity_provider.send_email_verification(account.account_id)

    def _register_seller(self, account: ProviderAccount) -> None:
        with self._unit_of_work() as repository:
            repository.register(Account(account.account_id, Role.SELLER, account.email))
