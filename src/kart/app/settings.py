"""The app's configuration, read from environment variables only.

The values come from `.env.example`, overridden by `.env` if one exists, which Docker Compose
hands to every container. The app never reads the files itself.
"""

from urllib.parse import quote

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    postgres_host: str
    postgres_user: str
    postgres_password: str
    postgres_db: str
    rabbitmq_host: str
    # The names the RabbitMQ image reads, so one variable sets both sides.
    rabbitmq_user: str = Field(validation_alias="RABBITMQ_DEFAULT_USER")
    rabbitmq_password: str = Field(validation_alias="RABBITMQ_DEFAULT_PASS")
    keycloak_url: str
    # Optional: without them, no traces are exported and errors are only logged.
    otlp_endpoint: str | None = Field(None, validation_alias="OTEL_EXPORTER_OTLP_ENDPOINT")
    sentry_dsn: str | None = None

    @property
    def database_url(self) -> str:
        credentials = _url_credentials(self.postgres_user, self.postgres_password)
        return f"postgresql+psycopg://{credentials}@{self.postgres_host}:5432/{self.postgres_db}"

    @property
    def rabbitmq_url(self) -> str:
        credentials = _url_credentials(self.rabbitmq_user, self.rabbitmq_password)
        return f"amqp://{credentials}@{self.rabbitmq_host}:5672/"


def _url_credentials(user: str, password: str) -> str:
    """`user:password` for a URL, with characters such as `@` and `/` escaped."""
    return f"{quote(user, safe='')}:{quote(password, safe='')}"
