"""Brings the kart realm's settings up to date in Keycloak: `python -m kart.app.keycloak_setup`.

Keycloak imports the realm only when it doesn't exist yet, so Compose runs this on every `up`
to reach an existing realm too. Applying the same settings again changes nothing.
"""

from kart.app.settings import Settings
from kart.contexts.identity.infrastructure.realm import apply_realm_settings

if __name__ == "__main__":
    settings = Settings()
    apply_realm_settings(settings.keycloak_admin, settings.smtp_server)
