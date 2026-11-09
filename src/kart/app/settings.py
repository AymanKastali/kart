"""The app's configuration: environment variables, falling back to `.env`.

`.env` (copied from `.env.example`) is the one place the local users, passwords and hosts
are set. Docker Compose hands it to every container and overrides the hosts; run on the
host with `uv run`, the app reads it from the working directory.
"""

from urllib.parse import quote

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # `.env` also holds the Keycloak admin login, which only Keycloak reads.
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    postgres_host: str
    postgres_user: str
    postgres_password: str
    postgres_db: str
    rabbitmq_host: str
    # The names the RabbitMQ image reads, so one variable sets both sides.
    rabbitmq_user: str = Field(validation_alias="RABBITMQ_DEFAULT_USER")
    rabbitmq_password: str = Field(validation_alias="RABBITMQ_DEFAULT_PASS")
    keycloak_url: str

    @property
    def database_url(self) -> str:
        credentials = _url_credentials(self.postgres_user, self.postgres_password)
        return f"postgresql://{credentials}@{self.postgres_host}:5432/{self.postgres_db}"

    @property
    def rabbitmq_url(self) -> str:
        credentials = _url_credentials(self.rabbitmq_user, self.rabbitmq_password)
        return f"amqp://{credentials}@{self.rabbitmq_host}:5672/"


def _url_credentials(user: str, password: str) -> str:
    """`user:password` for a URL, with characters such as `@` and `/` escaped."""
    return f"{quote(user, safe='')}:{quote(password, safe='')}"
