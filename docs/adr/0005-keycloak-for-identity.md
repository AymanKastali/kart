# Keycloak for Identity

Sign-up, email verification, password reset, sign-in and roles are a generic subdomain, so Kart uses a self-hosted Keycloak over OIDC instead of building authentication itself. We chose it over a hosted provider (Auth0, Clerk) to avoid vendor lock-in and free-tier limits while keeping a production-realistic setup, and over home-grown authentication because that teaches nothing about the marketplace and carries security risk.

## Consequences

- The rest of the system sees only a verified token carrying an Account id and one role. Nothing outside the Identity integration knows Keycloak exists.
- Other contexts learn about new Accounts (for example, the email address Notification needs) from Identity's integration events, not by querying Keycloak.
- Moving off Keycloak means migrating Accounts and password hashes.
