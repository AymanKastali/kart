"""Keycloak's hosted sign-in pages, driven as a person's browser would."""

import html
import re
from typing import TYPE_CHECKING

import httpx

from kart.contexts.identity.keycloak import REALM

if TYPE_CHECKING:
    from tests.mailpit import Email

# PKCE is required, and any 43-character value will do: the sign-in never completes.
_UNUSED_CODE_CHALLENGE = "a" * 43


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
            sign_in_page.url.join(_reset_link(sign_in_page.text)), headers=session
        )
        reset_page.raise_for_status()
        browser.post(
            reset_page.url.join(_form_action(reset_page.text)),
            data={"username": username},
            headers=session,
        ).raise_for_status()


def verify_email(email: Email) -> None:
    """Open the link in Keycloak's "Verify email" email, and confirm, as a person does."""
    with httpx.Client(follow_redirects=True) as browser:
        confirmation_page = browser.get(_link_in(email.text))
        confirmation_page.raise_for_status()
        # Confirming verifies the email, then redirects to carry on signing in, which a test
        # doesn't need.
        confirmed = browser.get(
            _proceed_link(confirmation_page.text),
            headers=_session(confirmation_page),
            follow_redirects=False,
        )
        if not confirmed.is_redirect:
            msg = f"Keycloak didn't confirm the email: {confirmed.status_code}"
            raise AssertionError(msg)


def _reset_link(page: str) -> str:
    match = re.search(r'href="([^"]*/login-actions/reset-credentials[^"]*)"', page)
    if match is None:
        msg = "the sign-in page offers no password reset"
        raise AssertionError(msg)
    return html.unescape(match[1])


def _form_action(page: str) -> str:
    match = re.search(r'<form[^>]*action="([^"]*)"', page)
    if match is None:
        msg = "the page has no form"
        raise AssertionError(msg)
    return html.unescape(match[1])


def _session(page: httpx.Response) -> dict[str, str]:
    # Keycloak marks its session cookies Secure, which a browser sends to localhost over plain
    # http but httpx doesn't, so they are passed on by hand.
    return {"Cookie": "; ".join(f"{name}={value}" for name, value in page.cookies.items())}


def _link_in(text: str) -> str:
    match = re.search(r"https?://\S+/login-actions/action-token\S+", text)
    if match is None:
        msg = "the email has no link"
        raise AssertionError(msg)
    return match[0]


def _proceed_link(page: str) -> str:
    match = re.search(r'href="([^"]*/login-actions/action-token[^"]*)"', page)
    if match is None:
        msg = "the page asks for no confirmation"
        raise AssertionError(msg)
    return html.unescape(match[1])
