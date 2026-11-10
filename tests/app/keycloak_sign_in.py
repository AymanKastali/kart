"""Keycloak's hosted sign-in pages, driven as a person's browser would."""

import html
import re
from typing import TYPE_CHECKING

import httpx

from kart.contexts.identity.infrastructure.keycloak import REALM

if TYPE_CHECKING:
    from tests.mailpit import Email

# PKCE is required, and any 43-character value will do: the sign-in never completes.
_UNUSED_CODE_CHALLENGE = "a" * 43
_RESET_LINK = r'href="([^"]*/login-actions/reset-credentials[^"]*)"'
_EMAILED_LINK = r"(https?://\S+/login-actions/action-token\S+)"
_PROCEED_LINK = r'href="([^"]*/login-actions/action-token[^"]*)"'
_FORM_ACTION = r'<form[^>]*action="([^"]*)"'


def request_password_reset(keycloak: str, username: str) -> None:
    """Ask for a reset link as a person does: through "Forgot password?" on the sign-in page."""
    with httpx.Client(follow_redirects=True) as browser:
        sign_in_page = browser.get(
            f"{keycloak}/realms/{REALM}/protocol/openid-connect/auth",
            params={
                # The realm's own account console: a client whose sign-in page is hosted.
                "client_id": "account-console",
                "redirect_uri": f"{keycloak}/realms/{REALM}/account/",
                "response_type": "code",
                "code_challenge": _UNUSED_CODE_CHALLENGE,
                "code_challenge_method": "S256",
            },
        )
        sign_in_page.raise_for_status()
        session = _session(sign_in_page)
        reset_page = browser.get(
            sign_in_page.url.join(
                _link_in(
                    sign_in_page.text, _RESET_LINK, "the sign-in page offers no password reset"
                )
            ),
            headers=session,
        )
        reset_page.raise_for_status()
        browser.post(
            reset_page.url.join(_link_in(reset_page.text, _FORM_ACTION, "the page has no form")),
            data={"username": username},
            headers=session,
        ).raise_for_status()


def verify_email(email: Email) -> None:
    """Open the link in Keycloak's "Verify email" email, and confirm, as a person does."""
    with httpx.Client(follow_redirects=True) as browser:
        confirmation_page = browser.get(
            _link_in(email.text, _EMAILED_LINK, "the email has no link")
        )
        confirmation_page.raise_for_status()
        # Confirming verifies the email, then redirects to carry on signing in, which a test
        # doesn't need.
        confirmed = browser.get(
            _link_in(confirmation_page.text, _PROCEED_LINK, "the page asks for no confirmation"),
            headers=_session(confirmation_page),
            follow_redirects=False,
        )
        if not confirmed.is_redirect:
            msg = f"Keycloak didn't confirm the email: {confirmed.status_code}"
            raise AssertionError(msg)


def _session(page: httpx.Response) -> dict[str, str]:
    # Keycloak marks its session cookies Secure, which a browser sends to localhost over plain
    # http but httpx doesn't, so they are passed on by hand.
    return {"Cookie": "; ".join(f"{name}={value}" for name, value in page.cookies.items())}


def _link_in(text: str, pattern: str, missing: str) -> str:
    """The link `pattern` captures, as a browser follows it."""
    match = re.search(pattern, text)
    if match is None:
        raise AssertionError(missing)
    return html.unescape(match[1])
