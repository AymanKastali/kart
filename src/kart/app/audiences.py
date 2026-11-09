"""Each API prefix serves one audience, and only that audience's role may call it."""

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from kart.contexts.identity.contracts import (
    AccessTokens,
    IdentityUnavailableError,
    InvalidAccessTokenError,
    Principal,
    Role,
)

# Anything outside these prefixes, such as /v1/storefront, is open to anyone.
_SIGNED_IN_PREFIXES = {f"/v1/{role}": role for role in Role}

_bearer_token = HTTPBearer(auto_error=False)


def principal_for_audience(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_token)],
) -> Principal | None:
    """The caller, if the route's audience needs one; None on an open route.

    Refuses a missing or invalid token with 401, and the wrong role with 403.
    """
    required_role = _required_role(request.url.path)
    if required_role is None:
        return None
    if credentials is None:
        raise _unauthenticated()
    access_tokens: AccessTokens = request.app.state.access_tokens
    try:
        principal = access_tokens.verify(credentials.credentials)
    except InvalidAccessTokenError:
        raise _unauthenticated() from None
    except IdentityUnavailableError:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE) from None
    if principal.role != required_role:
        raise HTTPException(status.HTTP_403_FORBIDDEN)
    return principal


def _required_role(path: str) -> Role | None:
    return next(
        (
            role
            for prefix, role in _SIGNED_IN_PREFIXES.items()
            if path == prefix or path.startswith(f"{prefix}/")
        ),
        None,
    )


def _unauthenticated() -> HTTPException:
    return HTTPException(status.HTTP_401_UNAUTHORIZED, headers={"WWW-Authenticate": "Bearer"})
