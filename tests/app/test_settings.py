import pytest
from pydantic import ValidationError

from kart.app.settings import Settings

# The same variables `.env` holds; the image-specific names are the ones Postgres and
# RabbitMQ read too.
ENVIRONMENT = {
    "POSTGRES_HOST": "postgres",
    "POSTGRES_USER": "kart",
    "POSTGRES_PASSWORD": "p@ss/word",
    "POSTGRES_DB": "kart",
    "RABBITMQ_HOST": "rabbitmq",
    "RABBITMQ_DEFAULT_USER": "kart",
    "RABBITMQ_DEFAULT_PASS": "secret",
    "KEYCLOAK_URL": "http://keycloak:8080",
}


@pytest.fixture
def environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name, value in ENVIRONMENT.items():
        monkeypatch.setenv(name, value)


@pytest.mark.usefixtures("environment")
def test_settings_build_the_connection_urls_from_environment_variables() -> None:
    settings = Settings()

    assert settings.database_url == "postgresql://kart:p%40ss%2Fword@postgres:5432/kart"
    assert settings.rabbitmq_url == "amqp://kart:secret@rabbitmq:5672/"
    assert settings.keycloak_url == "http://keycloak:8080"


@pytest.mark.usefixtures("environment")
@pytest.mark.parametrize("name", ENVIRONMENT)
def test_a_missing_setting_is_refused(monkeypatch: pytest.MonkeyPatch, name: str) -> None:
    monkeypatch.delenv(name)

    with pytest.raises(ValidationError, match=f"(?i){name}"):
        Settings()
