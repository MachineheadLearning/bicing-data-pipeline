# ADR-0003: Repository name, license and visibility

- **Status:** Accepted
- **Date:** 2026-11-15

## Context

The locked standards require feature branches merged into a protected `main` through pull
requests, with CI passing before merge. On GitHub Free, rulesets and branch protection are
enforced only in public repositories; private repositories need a paid plan. Secret scanning and
push protection are also free and on by default for public repositories. The project is a
portfolio piece, so its history is part of what reviewers see. The data source is CC0
(ADR-0001), so any code license is compatible.

## Options considered

- **Visibility:** public from day 1; private until day 5 (no enforced protection); private on
  GitHub Pro (about $4 a month, a cost outside the report).
- **Name:** `bicing-data-pipeline`, `barcelona-bikeshare-pipeline`, `bicing-gbfs-pipeline`.
- **License:** MIT, Apache-2.0, none.

## Decision

- **Name:** `bicing-data-pipeline`
- **License:** MIT
- **Visibility:** public from day 1

## Consequences

- `main` is protected from the first commit with a ruleset: no deletion, no force push,
  changes only through pull requests, and CI status checks required once the CI workflow exists.
- GitHub Actions minutes are free for the public repository.
- Work in progress is visible. Secrets must never reach the repo: `.env` is git-ignored, and
  `.env.example` holds names only. GitHub push protection is a backstop, not the main control.
- Commits use the author's GitHub noreply email so a personal address is not published.
- MIT lets anyone reuse the code with attribution. The README credits the data source.
