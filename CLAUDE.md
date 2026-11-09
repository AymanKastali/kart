## Agent skills

### Issue tracker

Issues live in GitHub Issues on AymanKastali/kart (via `gh`). See `docs/agents/issue-tracker.md`.

### Triage labels

Default vocabulary: needs-triage, needs-info, ready-for-agent, ready-for-human, wontfix. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: one `GLOSSARY.md` + `docs/adr/` at the repo root. See `docs/agents/domain.md`.

### Architecture diagrams

`docs/architecture/diagrams/` holds archify diagrams generated from `docs/architecture/context-map.md`, `docs/architecture/overview.md` and `docs/architecture/contexts/ordering.md`. They must never be out of sync with those docs. Whenever a context, relationship, integration event, key flow or Order state changes, update the matching `.archify.json`, re-render its `.html`, and commit both with the doc change. See `docs/architecture/diagrams/README.md`.

## Deployment

`docker compose -f deploy/compose.yaml up` is the whole deployment ([ADR-0007](docs/adr/0007-docker-compose-up-is-the-whole-deployment.md)). Never add a step someone runs by hand before or after it. Migrations, realm imports, queue setup and similar start-up work run automatically inside `compose up`, and they are safe to run again. Development checks run on the host through uv.
