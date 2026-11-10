# Coding standards

Every change to Kart is clean code, as Robert C. Martin describes it in *Clean Code*: code a
newcomer reads once and understands. This holds for every line, whoever or whatever writes it,
and is not saved for a later clean-up.

Tools enforce what they can, and fail CI when it's broken. The rest is judgement, and code review
checks it against this file.

## What the tools enforce

`scripts/static-checks.sh` runs them all. CI runs it, and so does a Claude Code hook before Claude
finishes a turn. Another hook formats and lints each Python file Claude edits, as it edits it.

| Rule | Tool | Limit |
|---|---|---|
| Small functions | ruff (`PLR0915`) | 15 statements |
| One thing per function | ruff (`C901`, `PLR0912`, `PLR0911`) | complexity 5, 6 branches, 4 returns |
| Few arguments | ruff (`PLR0913`, `PLR0917`) | 4 arguments, 3 of them positional; the rest keyword-only |
| No dead or speculative code | vulture, ruff (`F401`, `F841`, `ARG`, `ERA`) | nothing unused |
| No duplication | pylint (`duplicate-code`) | 4 similar lines |
| Everything else ruff checks | ruff (`select = ["ALL"]`) | |
| Types | ty | no errors or warnings |
| Context boundaries | import-linter | the contracts in `pyproject.toml` |
| A context's code sits in the classic layers | pytest (`tests/architecture`) | `domain`, `application`, `infrastructure` and `presentation` (its HTTP routes in `presentation/api`), beside its `contracts` and `migrations`, and nothing else |
| A context's layers depend inwards | import-linter | `presentation` and `infrastructure` build on `application`, which builds on `domain`; neither of the outer two imports the other |
| Use cases reach the outside world only through ports | import-linter | no `application` or `domain` imports a database, HTTP, broker, token or web library |
| Interfaces are Protocols | ruff (`TID251`) | no `abc.ABC`, `ABCMeta` or `abstractmethod` |

A `noqa` silences one rule on one line, and says why, as in
`# noqa: PLR0913, PLR0917 pika's four callback arguments, after two of ours`. It is for code a
library or framework shapes, never for code that is merely long.

## What review checks

### Names

- A name says what a thing is or does, in the words of [`GLOSSARY.md`](GLOSSARY.md): `Seller
  Application`, not `vendor_request`. Someone who doesn't know the library reads it correctly:
  `delivery_tag`, not `dt`; `apply_realm_settings`, not `sync`.
- Functions are verbs or questions (`apply_realm_settings`, `_retry_or_dead_letter`), values are nouns
  (`principal`, `smtp_server`). A boolean reads as a statement: `stopped`, `starttls`.
- One word per concept across the codebase. If it's an Account in one place it's never a user in
  another.
- No type or scope in a name (`settings_dict`, `m_engine`), and no numbers to tell two apart.

### Functions

- A function does one thing, at one level of abstraction. When its body mixes a policy with the
  details of carrying it out, the details move to a function named after what they do.
- No flag arguments that pick between two behaviours: write two functions.
- A function either changes something or answers something, not both. A name that says it does
  one thing does only that thing.
- Errors are exceptions, not return codes or `None` standing for failure.

### Modules and types

- A module, class or dataclass has one reason to change. When it changes for two unrelated
  reasons, split it.
- Values that always travel together become one type (`SmtpServer`, not a host, a port and a
  sender passed side by side).
- A domain idea gets its own type rather than a bare `str` or `int`, as the kernel's ids do.
- Depend on what a thing does, not how: a context reaches another only through its `contracts`,
  and a use case reaches the outside world only through its ports (see Design below).

### Design: SOLID, ports and adapters

Kart is object-oriented Python, and its design follows the SOLID principles.

- **Single responsibility.** A class has one reason to change. A use case decides; it doesn't
  also build SQL, call HTTP or parse JSON.
- **Dependency inversion.** A use case depends on what it needs, never on how that is done.
  Anything outside the process (a database, Keycloak, RabbitMQ, a payment provider, the clock
  when a rule depends on it) sits behind a **port** the use case declares in its context's
  `application/ports.py`, and an **adapter** in `infrastructure` implements it. The adapter is
  named after what it uses and the port it implements: `PostgresSellerApplicationRepository`,
  `KeycloakIdentityProvider`. A port that the app or another context calls, not a use case,
  lives in the context's `contracts` instead, as Identity's `AccessTokens` does. An event
  handler is a use case too: the inbox hands it its context's repository, never a session.
- **Interfaces are `typing.Protocol`s**, never `abc.ABC`. An adapter implements one by its shape
  alone, without inheriting from it, so the port never imports its adapters. The type checker
  checks the fit where the app hands the adapter in.
- **Interface segregation.** A port holds only what its use cases call, named in the context's
  own words. Two use cases that need different things get two ports.
- **Dependencies come in through the constructor.** No class builds its own collaborators or
  reads settings. `kart.app` is the one place that builds adapters and hands them in. An adapter
  that needs a library's client takes it too, and a function beside it builds both for the app
  (`keycloak_access_tokens`).
- **Open for extension.** When behaviour varies by kind (a courier, a payment method), each kind
  is a class that implements one Protocol (Strategy), so a new kind is a new class, not another
  branch in an `if` over the kinds.
- **Liskov substitution.** Anything that implements a Protocol keeps its promises: the same
  errors, the same meaning. Inherit only to satisfy a framework (`Exception`, `StrEnum`,
  Pydantic's `BaseModel`). Otherwise compose.
- **Patterns, by their usual names, where they fit.** Repository for an aggregate's storage,
  Unit of Work (`kart.shared.kernel.unit_of_work`) for a use case's transaction, Adapter for
  anything outside, Strategy for behaviour that varies. A pattern is used for the need in front
  of it, never in advance: a Protocol arrives with its first port, not for code inside the
  process that has one implementation and no outside world behind it.

### Comments

- Code says what it does. A comment says why, when the code can't: a constraint, a trade-off, a
  library quirk, the ADR behind it.
- No comment repeats the code, describes the change that introduced it, or keeps old code
  around. Git keeps history.
- Docstrings where they help a caller: what a function promises, not how it works.

### No speculative code

- Write only what the current ticket needs. No parameters, hooks, base classes or settings for a
  need nobody has yet. A type or function arrives with its first caller.
- Delete code the change made unused.

### Tests

- Tests are clean code too, held to every rule above.
- One behaviour per test, named as a sentence about it:
  `test_a_handler_that_always_fails_sends_the_event_to_the_dead_letter_queue`.
- Arrange, act and assert, separated by a blank line. Helpers hide set-up detail so the test reads
  as its specification.
