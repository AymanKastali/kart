"""Access tokens as Keycloak signs them: JWTs checked against the realm's public keys
(ADR-0005)."""

from typing import Any

import jwt

from kart.contexts.identity.contracts import (
    IdentityUnavailableError,
    InvalidAccessTokenError,
    Principal,
    Role,
)
from kart.contexts.identity.infrastructure.keycloak import REALM
from kart.shared.kernel.ids import AccountId

# The client a token must be issued for, so a token meant for another client is refused.
_API_CLIENT_ID = "kart-api"


def keycloak_access_tokens(identity_url: str) -> KeycloakAccessTokens:
    """The access tokens of the Keycloak at `identity_url`."""
    # Caches the realm's public keys, and fetches them again when a token names a key it hasn't
    # seen, so the keys can be rotated.
    return KeycloakAccessTokens(
        jwt.PyJWKClient(f"{identity_url}/realms/{REALM}/protocol/openid-connect/certs")
    )


class KeycloakAccessTokens:
    """Implements `AccessTokens` for the tokens Keycloak signs."""

    def __init__(self, signing_keys: jwt.PyJWKClient) -> None:
        self._signing_keys = signing_keys

    def verify(self, token: str) -> Principal:
        """The issuer isn't checked: only this realm's keys can sign a token that passes, and the
        issuer names whichever host the caller reached Keycloak at.
        """
        try:
            signing_key = self._signing_keys.get_signing_key_from_jwt(token)
            claims = jwt.decode(
                token,
                signing_key,
                algorithms=["RS256"],
                audience=_API_CLIENT_ID,
                options={"require": ["exp", "sub"]},
            )
        except jwt.PyJWKClientConnectionError as error:
            raise IdentityUnavailableError from error
        except jwt.PyJWTError as error:
            raise InvalidAccessTokenError from error
        return Principal(AccountId(claims["sub"]), _kart_role(claims))


def _kart_role(claims: dict[str, Any]) -> Role:
    # Keycloak's default roles, such as offline_access, sit beside Kart's own.
    realm_roles = claims.get("realm_access", {}).get("roles", [])
    kart_roles = [Role(name) for name in realm_roles if name in Role]
    if len(kart_roles) != 1:
        raise InvalidAccessTokenError
    return kart_roles[0]
