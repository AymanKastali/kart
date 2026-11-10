"""The environment variables a Kart process reads, set as Compose sets them."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pytest

# The same variables `.env` holds; the image-specific names are the ones Postgres, RabbitMQ
# and Keycloak read too.
ENVIRONMENT = {
    "POSTGRES_HOST": "postgres",
    "POSTGRES_USER": "kart",
    "POSTGRES_PASSWORD": "p@ss/word",
    "POSTGRES_DB": "kart",
    "RABBITMQ_HOST": "rabbitmq",
    "RABBITMQ_DEFAULT_USER": "kart",
    "RABBITMQ_DEFAULT_PASS": "secret",
    "KEYCLOAK_URL": "http://keycloak:8080",
    "KC_BOOTSTRAP_ADMIN_USERNAME": "admin",
    "KC_BOOTSTRAP_ADMIN_PASSWORD": "secret",
    "SMTP_HOST": "mailpit",
    "SMTP_PORT": "1025",
    "SMTP_FROM": "no-reply@kart.local",
    "SMTP_STARTTLS": "false",
}


def set_environment(monkeypatch: pytest.MonkeyPatch, **overrides: str) -> None:
    """Set `ENVIRONMENT` for the test, with `overrides` in place of some of its values."""
    for name, value in {**ENVIRONMENT, **overrides}.items():
        monkeypatch.setenv(name, value)
