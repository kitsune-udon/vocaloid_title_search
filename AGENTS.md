# Agent Rules

This file is the entry point for coding agents working in this repository.
Keep it short; detailed policy lives in tracked documents under `docs/`.

## Canonical Sources

Read these before editing tracked files:

- Documentation map and boundaries: [docs/README.md](docs/README.md)
- Development backlog: [docs/development-backlog.md](docs/development-backlog.md)
- Documentation backlog: [docs/documentation-improvement-backlog.md](docs/documentation-improvement-backlog.md)
- Privacy and secret handling: [docs/repository-privacy.md](docs/repository-privacy.md)
- Documentation quality: [docs/documentation-quality.md](docs/documentation-quality.md)

Do not treat personal skills, local notes, shell history, or untracked files as
project policy. If a rule should guide future work, add it to a tracked
document.

## Non-Negotiables

- Follow [docs/repository-privacy.md](docs/repository-privacy.md). Do not write
  real domains, IP addresses, usernames, emails, Cloudflare IDs, API tokens,
  secrets, cookies, passwords, or local config contents into tracked files.
- Use the placeholders defined in [docs/repository-privacy.md](docs/repository-privacy.md).
- Keep real environment files untracked, including `.env`, `.env.*`,
  `.dev.vars`, and `cloudflare/worker/wrangler.toml`.
- Update the canonical document instead of duplicating the same procedure in
  multiple places.
- Use project terms precisely: `生成`, `投入`, `deploy`, and
  `Terraform import` mean different operations.

## Work Intake

For non-trivial work, use [docs/development-backlog.md](docs/development-backlog.md).
For documentation-only work, use [docs/documentation-improvement-backlog.md](docs/documentation-improvement-backlog.md).

1. Find or create a task.
2. Check `Depends on` and blockers.
3. Identify `Owner`: `Agent`, `Human`, or `Shared`.
4. Confirm `Acceptance` and `Verification`.
5. Split broad tasks before implementing.

Agent-owned work can be completed in the repository with local verification.
Human-owned work requires private credentials, billing or account access,
production authority, irreversible external changes, or product judgment.
Shared work must state the handoff.

Do not mark a task `Done` just because files changed. Mark it done only when
acceptance and verification are satisfied, or when a human explicitly accepts
the remaining risk.

## Editing Flow

1. Locate the canonical document or code area using [docs/README.md](docs/README.md).
2. Check whether the change affects local SQLite, local D1, staging D1,
   production D1, Terraform-managed resources, Worker deploys, or Pages deploys.
3. Make the smallest coherent change.
4. Add or update verification steps for setup, API changes, deploy, D1投入, or
   Terraform changes.
5. If the work reveals process friction, add a `Process Improvement` item to
   the appropriate backlog. Use [docs/development-backlog.md](docs/development-backlog.md)
   for code/product/operations process, and
   [docs/documentation-improvement-backlog.md](docs/documentation-improvement-backlog.md)
   for documentation process.

Keep README as an entry point. Put detailed runbooks, design rationale, and
long procedures in `docs/`.

## Production Safety

Before running deploy, D1投入, or Terraform apply commands, confirm the target
environment and changed resource type in the user-facing update or final
instructions.

- Prefer dry-run or staging first.
- Do not run production deploy, production D1投入, or Terraform apply unless the
  user explicitly requests that operational action in the current turn.
- Do not infer permission from examples in documentation.

## Before Finishing

Run the privacy scan:

```bash
python3 tools/check_sensitive_values.py
```

For substantial code, API, Worker, frontend, or tooling changes, run:

```bash
tools/check_all.sh
```

For documentation changes, also apply the final review checklist in
[docs/documentation-quality.md](docs/documentation-quality.md).

If a check finds a problem, fix the tracked file. Do not add allowlist entries
unless the value is intentionally public project data.
