"""The app's configuration, read from environment variables only.

Docker Compose loads `.env` into the environment, so the app never reads a file itself.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    rabbitmq_url: str
    keycloak_url: str
