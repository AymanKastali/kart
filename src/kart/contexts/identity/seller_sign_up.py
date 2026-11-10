"""A business signs up for a Seller Account."""

from typing import TYPE_CHECKING

from kart.contexts.identity.contracts import Role
from kart.contexts.identity.keycloak_accounts import EmailTakenError, KeycloakAccounts
from kart.contexts.identity.registered_accounts import Account, register

if TYPE_CHECKING:
    from collections.abc import Callable
    from contextlib import AbstractContextManager

    from sqlalchemy.orm import Session

    from kart.contexts.identity.keycloak import KeycloakAdminLogin
    from kart.shared.kernel.ids import AccountId

# One transaction in Identity's schema, committed when the block succeeds.
type UnitOfWork = Callable[[], AbstractContextManager[Session]]


class SellerSignUp:
    def __init__(self, keycloak_admin: KeycloakAdminLogin, unit_of_work: UnitOfWork) -> None:
        self._keycloak_accounts = KeycloakAccounts(keycloak_admin)
        self._unit_of_work = unit_of_work

    def sign_up(self, email: str, password: str) -> AccountId:
        """A new Seller Account, which signs in once it has verified its email.

        Raises `EmailTakenError` if an Account has the email, and `SignUpRefusedError` if
        Keycloak refuses the Account, such as for a password its policy refuses.
        """
        try:
            account_id = self._keycloak_accounts.create_seller(email, password)
        except EmailTakenError:
            self._register_a_seller_left_unregistered(email)
            raise
        self._register(Account(account_id, Role.SELLER, email))
        self._keycloak_accounts.send_email_verification(account_id)
        return account_id

    def _register_a_seller_left_unregistered(self, email: str) -> None:
        """Finish a sign-up that stopped part way, such as in a crash, so a retry repairs it.

        Keycloak may hold the Account without its role, and Identity may not have registered
        it. Registering an Account again changes nothing, and another role's Account is left
        as it is.
        """
        account = self._keycloak_accounts.with_email(email)
        another_roles_account = bool(account.roles - {Role.SELLER})
        if another_roles_account:
            return
        if Role.SELLER not in account.roles:
            self._keycloak_accounts.make_seller(account.account_id)
        self._register(Account(account.account_id, Role.SELLER, account.email))

    def _register(self, account: Account) -> None:
        with self._unit_of_work() as session:
            register(session, account)
