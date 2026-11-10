# Ports and adapters in every context

Every bounded context is hexagonal, Supporting and generic ones included. A context's code sits in up to four layers: `domain`, `application`, `infrastructure` and `api`. A use case in `application` declares what it needs from outside the process as a port, a `typing.Protocol` in the context's `application/ports.py`. An adapter in `infrastructure` implements it, and `kart.app` builds the adapters and hands them to the use cases through their constructors. A use case runs its changes in a Unit of Work (`kart.shared.kernel.unit_of_work`) that hands it a repository bound to one transaction, so it never sees a database session.

We had kept Supporting and generic contexts as a thin service calling repository functions directly. But those services imported SQLAlchemy sessions and built their own Keycloak clients, so every use case was tied to how it was carried out, and the layering that kept Core contexts clean was only a convention elsewhere. One shape for every context, with import-linter enforcing it, costs a few small Protocols. In return, a use case can be read and changed without the storage or the identity provider in view, and the two never leak into each other.

We chose `typing.Protocol` over abstract base classes because Protocols are structural: an adapter implements a port by its shape alone, the port never imports its adapters, and the type checker checks the fit where `kart.app` wires them.

## Consequences

- import-linter enforces the layers (`api` and `infrastructure` build on `application`, which builds on `domain`), and forbids `application` and `domain` from importing a database, HTTP, broker, token or web library. ruff bans `abc.ABC` and `abstractmethod`.
- A layer is optional, so a context with no code has none, and gains each as it first needs it.
- How deep a model goes still depends on the subdomain: only Core contexts get rich domain models.
- Identity's `contracts` became a package. Its FastAPI glue, which hands the signed-in Principal from the app to a route, moved to `contracts.signed_in`, so a use case that needs a `Role` doesn't pull in FastAPI.
