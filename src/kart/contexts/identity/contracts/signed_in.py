"""The Principal behind a request to a signed-in audience's route, handed from the app, which
let it through, to the route, which serves it."""

from typing import TYPE_CHECKING

from fastapi import Request  # noqa: TC002 FastAPI reads the annotation to pass the request

if TYPE_CHECKING:
    from kart.contexts.identity.contracts import Principal


def keep_signed_in_principal(request: Request, principal: Principal) -> None:
    """Keep the Principal the app let through to a signed-in audience's route."""
    request.state.principal = principal


def signed_in_principal(request: Request) -> Principal:
    """The Principal behind a request to a signed-in audience's route, which the app has already
    let through for its role. A route asks for it as a FastAPI dependency."""
    return request.state.principal
