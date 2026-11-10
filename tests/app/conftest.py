from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import make_url
from testcontainers.core.container import DockerContainer
from testcontainers.core.wait_strategies import LogMessageWaitStrategy

from kart.app.api import create_app
from kart.app.migrate import migrate
from tests.app.environment import set_environment
from tests.app.keycloak import ADMIN, set_up_realm
from tests.conftest import new_database

if TYPE_CHECKING:
    from collections.abc import Iterator

    from testcontainers.community.postgres import PostgresContainer
    from testcontainers.core.network import Network

    from tests.mailpit import Mailpit

# tests/app/<this file> -> the repository root.
REALM_FILE = Path(__file__).resolve().parents[2] / "keycloak/kart-realm.json"
KEYCLOAK_PORT = 8080


@pytest.fixture(scope="session")
def keycloak(network: Network, mailpit: Mailpit) -> Iterator[str]:  # noqa: ARG001 sends to it
    """The URL of a Keycloak, configured as in Compose, that has imported the kart realm."""
    container = (
        DockerContainer("quay.io/keycloak/keycloak:26.4")
        .with_command("start-dev --import-realm")
        .with_env("KC_BOOTSTRAP_ADMIN_USERNAME", ADMIN.username)
        .with_env("KC_BOOTSTRAP_ADMIN_PASSWORD", ADMIN.password)
        .with_volume_mapping(str(REALM_FILE), "/opt/keycloak/data/import/kart-realm.json")
        .with_network(network)
        .with_exposed_ports(KEYCLOAK_PORT)
        .waiting_for(LogMessageWaitStrategy("started in").with_startup_timeout(120))
    )
    with container:
        url = f"http://{container.get_container_host_ip()}:{container.get_exposed_port(KEYCLOAK_PORT)}"
        set_up_realm(url)
        yield url


@pytest.fixture(scope="module")
def database_url(postgres: PostgresContainer) -> str:
    """A migrated database, shared by the tests of one module."""
    url = new_database(postgres)
    migrate(url)
    return url


@pytest.fixture
def api(keycloak: str, database_url: str, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """The real app, against the test Keycloak and the module's database."""
    url = make_url(database_url)
    set_environment(
        monkeypatch,
        KEYCLOAK_URL=keycloak,
        KC_BOOTSTRAP_ADMIN_USERNAME=ADMIN.username,
        KC_BOOTSTRAP_ADMIN_PASSWORD=ADMIN.password,
        POSTGRES_HOST=str(url.host),
        POSTGRES_PORT=str(url.port),
        POSTGRES_USER=str(url.username),
        POSTGRES_PASSWORD=str(url.password),
        POSTGRES_DB=str(url.database),
    )
    with TestClient(create_app()) as client:
        yield client
