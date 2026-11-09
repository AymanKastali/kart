"""Who is calling: the Principal behind an access token, which is all other contexts see of an
Account. Only Identity knows the tokens come from Keycloak (ADR-0005)."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

import jwt

from kart.shared.kernel.ids import AccountId

_REALM = "kart"
# The client a token must be issued for, so a token meant for another client is refused.
_API_CLIENT_ID = "kart-api"


class Role(StrEnum):
    CUSTOMER = "customer"
    SELLER = "seller"
    OPERATOR = "operator"


@dataclass(frozen=True, slots=True)
class Principal:
    """The Account behind a request, with its one role."""

    account_id: AccountId
    role: Role


class InvalidAccessTokenError(Exception):
    """The token is not a valid, unexpired Kart token for exactly one role."""


class IdentityUnavailableError(Exception):
    """The keys that sign access tokens can't be fetched, so no token can be checked."""


class AccessTokens:
    def __init__(self, identity_url: str) -> None:
        # Caches the realm's public keys, and fetches them again when a token names a key it
        # hasn't seen, so the keys can be rotated.
        self._signing_keys = jwt.PyJWKClient(
            f"{identity_url}/realms/{_REALM}/protocol/openid-connect/certs"
        )

    def verify(self, token: str) -> Principal:
        """The Principal the token was issued to.

        The issuer isn't checked: only this realm's keys can sign a token that passes, and the
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
