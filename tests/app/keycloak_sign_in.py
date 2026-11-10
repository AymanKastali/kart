"""Keycloak's hosted sign-in pages, driven as a person's browser would."""

import html
import re

import httpx

from kart.contexts.identity.realm import REALM

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
        # Keycloak marks its session cookies Secure, which a browser sends to localhost over
        # plain http but httpx doesn't, so they are passed on by hand.
        session = {
            "Cookie": "; ".join(f"{name}={value}" for name, value in sign_in_page.cookies.items())
        }
        reset_page = browser.get(
            sign_in_page.url.join(_reset_link(sign_in_page.text)), headers=session
        )
        reset_page.raise_for_status()
        browser.post(
            reset_page.url.join(_form_action(reset_page.text)),
            data={"username": username},
            headers=session,
        ).raise_for_status()


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
