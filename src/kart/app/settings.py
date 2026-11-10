"""The app's configuration, read from environment variables only.

The values come from `.env.example`, overridden by `.env` if one exists, which Docker Compose
hands to every container. The app never reads the files itself.
"""

from typing import Self
from urllib.parse import quote

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings

from kart.contexts.identity.keycloak import KeycloakAdminLogin
from kart.contexts.identity.realm import SmtpLogin, SmtpServer


class Settings(BaseSettings):
    postgres_host: str
    postgres_port: int = 5432
    postgres_user: str
    postgres_password: str
    postgres_db: str
    rabbitmq_host: str
    # The names the RabbitMQ image reads, so one variable sets both sides.
    rabbitmq_user: str = Field(validation_alias="RABBITMQ_DEFAULT_USER")
    rabbitmq_password: str = Field(validation_alias="RABBITMQ_DEFAULT_PASS")
    keycloak_url: str
    # The administrator the Keycloak image creates, so one variable sets both sides.
    keycloak_admin_username: str = Field(validation_alias="KC_BOOTSTRAP_ADMIN_USERNAME")
    keycloak_admin_password: str = Field(validation_alias="KC_BOOTSTRAP_ADMIN_PASSWORD")
    smtp_host: str
    smtp_port: int
    smtp_from: str
    smtp_starttls: bool
    # Only for an SMTP server that asks for a login, such as Resend's.
    smtp_username: str | None = None
    smtp_password: str | None = None
    # Optional: without them, no traces are exported and errors are only logged.
    otlp_endpoint: str | None = Field(None, validation_alias="OTEL_EXPORTER_OTLP_ENDPOINT")
    sentry_dsn: str | None = None

    @property
    def database_url(self) -> str:
        credentials = _url_credentials(self.postgres_user, self.postgres_password)
        return f"postgresql+psycopg://{credentials}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"

    @property
    def rabbitmq_url(self) -> str:
        credentials = _url_credentials(self.rabbitmq_user, self.rabbitmq_password)
        return f"amqp://{credentials}@{self.rabbitmq_host}:5672/"

    @model_validator(mode="after")
    def _smtp_login_is_whole(self) -> Self:
        if (self.smtp_username is None) != (self.smtp_password is None):
            msg = "SMTP_USERNAME and SMTP_PASSWORD are set together, or neither is"
            raise ValueError(msg)
        return self

    @property
    def keycloak_admin(self) -> KeycloakAdminLogin:
        return KeycloakAdminLogin(
            url=self.keycloak_url,
            username=self.keycloak_admin_username,
            password=self.keycloak_admin_password,
        )

    @property
    def smtp_server(self) -> SmtpServer:
        return SmtpServer(
            host=self.smtp_host,
            port=self.smtp_port,
            sender=self.smtp_from,
            starttls=self.smtp_starttls,
            login=self._smtp_login,
        )

    @property
    def _smtp_login(self) -> SmtpLogin | None:
        if self.smtp_username is None or self.smtp_password is None:
            return None
        return SmtpLogin(self.smtp_username, self.smtp_password)


def _url_credentials(user: str, password: str) -> str:
    """`user:password` for a URL, with characters such as `@` and `/` escaped."""
    return f"{quote(user, safe='')}:{quote(password, safe='')}"
