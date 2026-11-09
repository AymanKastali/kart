import pytest
from pydantic import ValidationError

from kart.app.settings import Settings

ENVIRONMENT = {
    "DATABASE_URL": "postgresql://kart:kart@postgres:5432/kart",
    "RABBITMQ_URL": "amqp://kart:kart@rabbitmq:5672/",
    "KEYCLOAK_URL": "http://keycloak:8080",
}


@pytest.fixture
def environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name, value in ENVIRONMENT.items():
        monkeypatch.setenv(name, value)


@pytest.mark.usefixtures("environment")
def test_settings_come_from_environment_variables() -> None:
    settings = Settings()

    assert settings.database_url == "postgresql://kart:kart@postgres:5432/kart"
    assert settings.rabbitmq_url == "amqp://kart:kart@rabbitmq:5672/"
    assert settings.keycloak_url == "http://keycloak:8080"


@pytest.mark.usefixtures("environment")
@pytest.mark.parametrize("name", ENVIRONMENT)
def test_a_missing_setting_is_refused(monkeypatch: pytest.MonkeyPatch, name: str) -> None:
    monkeypatch.delenv(name)

    with pytest.raises(ValidationError, match=name.lower()):
        Settings()
