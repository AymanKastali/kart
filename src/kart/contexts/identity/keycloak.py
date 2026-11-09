"""Turns a Keycloak access token into a Principal. Nothing outside Identity knows Keycloak
exists (ADR-0005)."""

import jwt

from kart.contexts.identity.contracts import Principal, Role
from kart.shared.kernel.ids import AccountId

REALM = "kart"
# The client tokens must be issued for, so a token meant for another client is refused.
AUDIENCE = "kart-api"


class InvalidAccessTokenError(Exception):
    """The token is not a valid, unexpired Kart token for exactly one role."""


class KeycloakAccessTokens:
    def __init__(self, keycloak_url: str) -> None:
        # Caches the realm's public keys, and fetches them again when a token names a key it
        # hasn't seen, so Keycloak can rotate its keys.
        self._signing_keys = jwt.PyJWKClient(
            f"{keycloak_url}/realms/{REALM}/protocol/openid-connect/certs"
        )

    def verify(self, token: str) -> Principal:
        # The issuer isn't checked: only this realm's keys can sign a token that passes, and
        # the issuer names whichever host the caller reached Keycloak at.
        try:
            signing_key = self._signing_keys.get_signing_key_from_jwt(token)
            claims = jwt.decode(token, signing_key, algorithms=["RS256"], audience=AUDIENCE)
        except jwt.PyJWTError as error:
            raise InvalidAccessTokenError from error
        return Principal(AccountId(claims["sub"]), _the_one_role(claims))


def _the_one_role(claims: dict) -> Role:
    # Keycloak's default roles, such as offline_access, sit beside Kart's own.
    roles = [Role(name) for name in claims.get("realm_access", {}).get("roles", []) if name in Role]
    if len(roles) != 1:
        raise InvalidAccessTokenError
    return roles[0]
