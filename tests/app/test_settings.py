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

    assert settings.database_url == "postgresql+psycopg://kart:p%40ss%2Fword@postgres:5432/kart"
    assert settings.rabbitmq_url == "amqp://kart:secret@rabbitmq:5672/"
    assert settings.keycloak_url == "http://keycloak:8080"


@pytest.mark.usefixtures("environment")
@pytest.mark.parametrize("name", ENVIRONMENT)
def test_a_missing_setting_is_refused(monkeypatch: pytest.MonkeyPatch, name: str) -> None:
    monkeypatch.delenv(name)

    with pytest.raises(ValidationError, match=f"(?i){name}"):
        Settings()


@pytest.mark.usefixtures("environment")
def test_tracing_and_error_reporting_are_off_unless_configured() -> None:
    settings = Settings()

    assert settings.otlp_endpoint is None
    assert settings.sentry_dsn is None


@pytest.mark.usefixtures("environment")
def test_tracing_and_error_reporting_read_their_standard_variables(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://jaeger:4318")
    monkeypatch.setenv("SENTRY_DSN", "https://key@sentry.example/1")

    settings = Settings()

    assert settings.otlp_endpoint == "http://jaeger:4318"
    assert settings.sentry_dsn == "https://key@sentry.example/1"
