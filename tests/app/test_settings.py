import pytest
from pydantic import ValidationError

from kart.app.settings import Settings
from kart.contexts.identity.realm import KeycloakAdminLogin, SmtpLogin, SmtpServer

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
def test_settings_say_how_to_administer_keycloak_and_where_to_send_email() -> None:
    settings = Settings()

    assert settings.keycloak_admin == KeycloakAdminLogin("http://keycloak:8080", "admin", "secret")
    assert settings.smtp_server == SmtpServer(
        "mailpit", 1025, "no-reply@kart.local", starttls=False
    )


@pytest.mark.usefixtures("environment")
def test_an_smtp_server_that_asks_for_a_login_gets_one(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SMTP_STARTTLS", "true")
    monkeypatch.setenv("SMTP_USERNAME", "resend")
    monkeypatch.setenv("SMTP_PASSWORD", "re_key")

    settings = Settings()

    assert settings.smtp_server.starttls is True
    assert settings.smtp_server.login == SmtpLogin("resend", "re_key")


@pytest.mark.usefixtures("environment")
@pytest.mark.parametrize("name", ["SMTP_USERNAME", "SMTP_PASSWORD"])
def test_half_an_smtp_login_is_refused(monkeypatch: pytest.MonkeyPatch, name: str) -> None:
    monkeypatch.setenv(name, "set")

    with pytest.raises(ValidationError, match="SMTP_USERNAME and SMTP_PASSWORD"):
        Settings()


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
