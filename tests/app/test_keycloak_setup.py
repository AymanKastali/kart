from typing import TYPE_CHECKING

from kart.contexts.identity.contracts import Role
from tests.app.keycloak import KeycloakAdmin, email_address, set_up_realm
from tests.app.keycloak_sign_in import request_password_reset
from tests.mailpit import SMTP_SERVER

if TYPE_CHECKING:
    from tests.mailpit import Mailpit


def test_a_forgotten_password_is_reset_through_a_link_sent_by_email(
    keycloak: str, mailpit: Mailpit
) -> None:
    seller = KeycloakAdmin(keycloak).new_account([Role.SELLER])

    request_password_reset(keycloak, seller.username)

    email = mailpit.email_to(email_address(seller))
    assert email.subject == "Reset password"
    assert "/realms/kart/login-actions/action-token" in email.text


def test_setting_up_the_realm_again_changes_nothing(keycloak: str) -> None:
    # The fixture has set the realm up once already.
    admin = KeycloakAdmin(keycloak)
    before = admin.realm()

    set_up_realm(keycloak)

    assert admin.realm() == before


def test_the_realm_is_given_its_email_server_and_password_rules(keycloak: str) -> None:
    settings = KeycloakAdmin(keycloak).realm()

    assert settings["verifyEmail"] is True
    assert settings["resetPasswordAllowed"] is True
    assert settings["passwordPolicy"] == "length(8) and notUsername and notEmail"
    assert settings["smtpServer"]["host"] == SMTP_SERVER.host
    assert settings["smtpServer"]["from"] == SMTP_SERVER.sender
