from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from testcontainers.core.container import DockerContainer
from testcontainers.core.wait_strategies import LogMessageWaitStrategy

from tests.app.keycloak import ADMIN

if TYPE_CHECKING:
    from collections.abc import Iterator

# tests/app/<this file> -> the repository root.
REALM_FILE = Path(__file__).resolve().parents[2] / "deploy/keycloak/kart-realm.json"


@pytest.fixture(scope="session")
def keycloak() -> Iterator[str]:
    """The URL of a Keycloak, configured as in Compose, that has imported the kart realm."""
    container = (
        DockerContainer("quay.io/keycloak/keycloak:26.4")
        .with_command("start-dev --import-realm")
        .with_env("KC_BOOTSTRAP_ADMIN_USERNAME", ADMIN.username)
        .with_env("KC_BOOTSTRAP_ADMIN_PASSWORD", ADMIN.password)
        .with_volume_mapping(str(REALM_FILE), "/opt/keycloak/data/import/kart-realm.json")
        .with_exposed_ports(8080)
        .waiting_for(LogMessageWaitStrategy("started in").with_startup_timeout(120))
    )
    with container:
        yield f"http://{container.get_container_host_ip()}:{container.get_exposed_port(8080)}"
