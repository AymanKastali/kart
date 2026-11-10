"""The emails a test Mailpit caught, through its API."""

import time
from dataclasses import dataclass

import httpx

from kart.contexts.identity.realm import SmtpServer

# Where the test Mailpit takes email, as Compose's does.
SMTP_SERVER = SmtpServer("mailpit", 1025, "no-reply@kart.local", starttls=False)
MAILPIT_API_PORT = 8025

# How long an email may take to arrive: some are sent after the request that caused them.
_ARRIVAL_TIMEOUT_SECONDS = 10


@dataclass(frozen=True, slots=True)
class Email:
    subject: str
    text: str


class Mailpit:
    def __init__(self, api_url: str) -> None:
        self._client = httpx.Client(base_url=f"{api_url}/api/v1")

    def email_to(self, address: str) -> Email:
        """The one email sent to `address`, waiting for it to arrive."""
        [email] = self.emails_to(address, count=1)
        return email

    def emails_to(self, address: str, *, count: int) -> list[Email]:
        """Every email sent to `address`, waiting for at least `count` of them to arrive."""
        deadline = time.monotonic() + _ARRIVAL_TIMEOUT_SECONDS
        while len(messages := self._messages_to(address)) < count:
            if time.monotonic() > deadline:
                msg = f"{count} emails to {address} didn't arrive"
                raise AssertionError(msg)
            time.sleep(0.2)
        return [self._email(message["ID"]) for message in messages]

    def _messages_to(self, address: str) -> list[dict]:
        response = self._client.get("/search", params={"query": f'to:"{address}"'})
        response.raise_for_status()
        return response.json()["messages"]

    def _email(self, message_id: str) -> Email:
        response = self._client.get(f"/message/{message_id}")
        response.raise_for_status()
        message = response.json()
        return Email(subject=message["Subject"], text=message["Text"])
