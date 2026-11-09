# A Postgres role per context, switched to inside each unit of work

Each context owns its own schema ([ADR-0003](0003-modular-monolith-with-strict-context-boundaries.md)), and import-linter keeps contexts out of each other's code. Nothing kept them out of each other's tables: one SQL string naming `ordering.orders` from inside Catalog would work. So each context gets a Postgres role (`NOLOGIN`) with the context's name, which owns its schema and everything in it, and no other role is granted anything there.

The app logs in once and shares one engine and pool. Each unit of work starts with `SET LOCAL ROLE <context>` and `SET LOCAL search_path TO <context>`, so for that transaction Postgres checks every statement against the context's role and refuses one that touches another schema. Migrations run as the context's role too, so the objects they create belong to it.

We considered one login role per context, with its own engine. It is the stronger boundary, but it needs ten connection pools and ten passwords in the configuration. We also considered relying on review alone and rejected it, because the mistake it guards against is easy to make and silent.

## Consequences

- The boundary guards against mistakes, not against hostile code: a context could run `RESET ROLE` to get the login role back. Review catches that, and nothing in a context has a reason to do it.
- The login role must be able to switch to every context role. The `migrate` command creates the roles and schemas before any revision runs, so it needs a role that can create roles (in Compose, the image's superuser).
- The `migrate` command creates each context's role and schema itself, before Alembic runs, because Alembic creates the version table inside the schema first. So each context's first revision is an empty baseline that starts its history, and downgrading to base leaves the schema and role in place.
- A query that genuinely needs data from two contexts can't be written. That is the point: it goes through the other context's `contracts` instead.
