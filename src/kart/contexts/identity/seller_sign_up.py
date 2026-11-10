"""A business signs up for a Seller Account."""

from typing import TYPE_CHECKING

from kart.contexts.identity.contracts import Role
from kart.contexts.identity.infrastructure.registered_accounts import Account, register
from kart.contexts.identity.keycloak_accounts import EmailTakenError, KeycloakAccounts

if TYPE_CHECKING:
    from collections.abc import Callable
    from contextlib import AbstractContextManager

    from sqlalchemy.orm import Session

    from kart.contexts.identity.keycloak import KeycloakAdminLogin
    from kart.contexts.identity.keycloak_accounts import Credentials
    from kart.shared.kernel.ids import AccountId

# One transaction in Identity's schema, committed when the block succeeds.
type UnitOfWork = Callable[[], AbstractContextManager[Session]]


class SellerSignUp:
    def __init__(self, keycloak_admin: KeycloakAdminLogin, unit_of_work: UnitOfWork) -> None:
        self._keycloak_accounts = KeycloakAccounts(keycloak_admin)
        self._unit_of_work = unit_of_work

    def sign_up(self, credentials: Credentials) -> AccountId:
        """A new Seller Account, which signs in once it has verified its email.

        Raises `EmailTakenError` if an Account has the email, and `SignUpRefusedError` if
        Keycloak refuses the Account, such as for a password its policy refuses.
        """
        try:
            account = self._keycloak_accounts.create_seller(credentials)
        except EmailTakenError:
            self._finish_a_sign_up_that_stopped_part_way(credentials.email)
            raise
        self._register(Account(account.account_id, Role.SELLER, account.email))
        self._keycloak_accounts.send_email_verification(account.account_id)
        return account.account_id

    def _finish_a_sign_up_that_stopped_part_way(self, email: str) -> None:
        """Let a retry repair a sign-up that stopped after Keycloak created the Seller Account,
        such as in a crash before Identity registered it, or when its verification email
        couldn't be sent.

        Registering an Account again changes nothing, and the link is emailed again until the
        Account has verified its email. Any other Account with the email is left as it is.
        """
        account = self._keycloak_accounts.with_email(email)
        if account is None or account.roles != {Role.SELLER}:
            return
        self._register(Account(account.account_id, Role.SELLER, account.email))
        if not account.email_verified:
            self._keycloak_accounts.send_email_verification(account.account_id)

    def _register(self, account: Account) -> None:
        with self._unit_of_work() as session:
            register(session, account)
