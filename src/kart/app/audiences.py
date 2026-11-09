"""Each API prefix serves one audience, and only that audience's role may call it."""

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from kart.contexts.identity.contracts import Principal, Role
from kart.contexts.identity.keycloak import InvalidAccessTokenError, KeycloakAccessTokens

_ROLE_FOR_PREFIX = {
    "/v1/customer/": Role.CUSTOMER,
    "/v1/seller/": Role.SELLER,
    "/v1/operator/": Role.OPERATOR,
}

_bearer_token = HTTPBearer(auto_error=False)


def principal_for_audience(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_token)],
) -> Principal | None:
    """The caller, if the route's audience needs one; None on an anonymous route.

    Refuses a missing or invalid token with 401, and the wrong role with 403.
    """
    required_role = _required_role(request.url.path)
    if required_role is None:
        return None
    if credentials is None:
        raise _unauthenticated()
    access_tokens: KeycloakAccessTokens = request.app.state.access_tokens
    try:
        principal = access_tokens.verify(credentials.credentials)
    except InvalidAccessTokenError:
        raise _unauthenticated() from None
    if principal.role != required_role:
        raise HTTPException(status.HTTP_403_FORBIDDEN)
    return principal


def _required_role(path: str) -> Role | None:
    return next(
        (role for prefix, role in _ROLE_FOR_PREFIX.items() if path.startswith(prefix)), None
    )


def _unauthenticated() -> HTTPException:
    return HTTPException(status.HTTP_401_UNAUTHORIZED, headers={"WWW-Authenticate": "Bearer"})
