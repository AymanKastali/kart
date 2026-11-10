from typing import TYPE_CHECKING

from tests.app.keycloak import KeycloakAdmin, request_password_reset, set_up_realm

if TYPE_CHECKING:
    from tests.mailpit import Mailpit


def test_a_forgotten_password_is_reset_through_a_link_sent_by_email(
    keycloak: str, mailpit: Mailpit
) -> None:
    login = KeycloakAdmin(keycloak).new_account(["seller"])

    request_password_reset(keycloak, login.username)

    email = mailpit.email_to(f"{login.username}@kart.local")
    assert email.subject == "Reset password"
    assert "/realms/kart/login-actions/action-token" in email.text


def test_setting_up_the_realm_again_changes_nothing(keycloak: str) -> None:
    # The fixture has set the realm up once already.
    admin = KeycloakAdmin(keycloak)
    before = admin.realm()

    set_up_realm(keycloak)

    assert admin.realm() == before


def test_the_realm_has_its_email_verification_password_reset_and_policy(keycloak: str) -> None:
    settings = KeycloakAdmin(keycloak).realm()

    assert settings["verifyEmail"] is True
    assert settings["resetPasswordAllowed"] is True
    assert settings["passwordPolicy"] == "length(8) and notUsername and notEmail"
    assert settings["smtpServer"]["host"] == "mailpit"
    assert settings["smtpServer"]["from"] == "no-reply@kart.local"
