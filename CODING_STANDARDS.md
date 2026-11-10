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
- Depend on what a thing does, not how: a context reaches another only through its `contracts`.

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
