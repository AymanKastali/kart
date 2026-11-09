"""The app's configuration, read from environment variables only.

Docker Compose sets them for each process (see `deploy/compose.yaml`); the app reads no file.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    rabbitmq_url: str
    keycloak_url: str
