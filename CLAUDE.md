# CLAUDE.md — bicing-data-pipeline

Standing instructions for Claude Code. Read this file and the ADRs in `docs/adr/` before every task.

## What this project is

A batch data pipeline on live Barcelona Bicing bike-share data (official GBFS 3.0 feed). It is a
portfolio project. The author must be able to explain every line, so avoid complex code if there

are more simple, similarly effective and efficient alternatives.

Flow: **ingest** (fetch, validate with Pydantic, write raw files) → **load** (into the warehouse)
→ **dbt** (staging, intermediate, marts, snapshots, tests). Airflow runs these three steps in order.

## How you work here

* Do **only** the task in the prompt. Touch only the folders the prompt allows.
* **Stop and ask** instead of guessing when you hit a decision the prompt or the ADRs don't cover:
architecture, a new dependency, naming, data rules, or anything that changes scope.
* **No new tools or dependencies** beyond those listed below unless the prompt explicitly allows
them.
* Every task ends with passing tests (`uv run pytest`) and passing lint (`uv run ruff check .` and
`uv run ruff format --check .`).
* Finish with a summary: what changed (file by file), any choices you had to make and why, and the
exact commands to verify the result.
* Never commit secrets. Configuration comes from environment variables, every one of which is
documented in `.env.example` with no real values. `.env` is git-ignored.
* Work on the current feature branch. Never push to `main`.

## Locked stack and versions

|Area|Choice|
|-|-|
|Language|Python 3.12 with type hints everywhere; SQL; YAML|
|Python tooling|`uv` (deps and lock), `ruff` (lint and format), `pytest`, `pre-commit`|
|Validation|Pydantic v2|
|Raw storage|Local folder `data/` (local mode), Amazon S3 (cloud mode)|
|Warehouse|DuckDB (local mode and CI), Snowflake (cloud mode)|
|Transformation|dbt-core 1.12.7, dbt-snowflake 1.12.5, dbt-duckdb 1.11.1|
|Orchestration|Apache Airflow 3.4.0 in Docker Compose (official image, Python 3.12)|
|CI|GitHub Actions: ruff, pytest, `dbt build` on DuckDB with fixture files, no cloud credentials|

**Out of scope, never add:** Lambda, EventBridge, Terraform, PySpark, Kafka or any streaming,
Streamlit or dashboards, Kubernetes, managed Airflow, ML, other cities, other data sources.

## Dependency layout (ADR-0006)

* **Local development and CI:** one `uv` project (`pyproject.toml` plus `uv.lock`) with the
ingestion code, dbt-core and both adapters, and the dev tools. **Airflow is not installed in
it.**
* **Airflow image (day 2):** Airflow plus the ingestion package, installed with Airflow's
constraints file. dbt lives in its own virtual environment inside the image.
* **Ingestion dependencies must fit inside Airflow 3.4.0's constraints for Python 3.12.** Don't
add an ingestion dependency without that check.

## Execution modes (only configuration changes between them)

|Mode|Raw storage|Warehouse|Orchestration|
|-|-|-|-|
|local|`data/` folder|DuckDB|Airflow in Docker Compose|
|ci|fixture files in the repo|DuckDB|none (GitHub Actions runs the steps)|
|cloud|S3 bucket|Snowflake|Airflow in Docker Compose|

- **AWS region:** `eu-north-1` (ADR-0004). Read it from configuration (`AWS_REGION`); never hard-code it.

## Data source (ADR-0001, ADR-0002)

* Auto-discovery: `https://barcelona.publicbikesystem.net/customer/gbfs/v3.0/gbfs.json`. The
license is CC0. No authentication.
* Feeds:

  * `station\\\_status` every **5 minutes**
  * `station\\\_information` and `vehicle\\\_types` every **hour**
* GBFS 3.0 specifics:

  * `last\\\_updated` and `last\\\_reported` are RFC3339 strings in UTC, with or without milliseconds
(for example `2026-11-14T23:02:04Z` and `2026-11-14T22:59:47.557Z`).
  * Names are lists of `{text, language}` objects.
  * `post\\\_code` is optional.
  * `ttl` is 0 and there is no ETag.
* Be polite to the feed: a short timeout, a few retries with backoff, a descriptive User-Agent,
and no parallel hammering.

## Raw file layout (ADR-0007)

```
raw/gbfs/feed=<feed>/dt=YYYY-MM-DD/<feed>\\\_YYYYMMDDTHHMMSSZ.json.gz
quarantine/gbfs/feed=<feed>/dt=YYYY-MM-DD/<feed>\\\_YYYYMMDDTHHMMSSZ.payload.json.gz
quarantine/gbfs/feed=<feed>/dt=YYYY-MM-DD/<feed>\\\_YYYYMMDDTHHMMSSZ.records.jsonl
```

* The timestamp and `dt` come from the feed's own `last\\\_updated`, in UTC.
* The payload bytes are gzipped **unchanged**: no parsing and re-serialising before the raw write.
* **Write-once:** never overwrite. If the file already exists, skip it and log that.
* If the payload fails top-level validation, write it to `quarantine/…payload.json.gz` only, and
never to `raw/`. If `last\\\_updated` is missing or unparseable, use the fetch time in UTC for the
name.
* If station records fail validation inside a valid payload, the full payload still goes to
`raw/`. The invalid records and their error reasons go to `quarantine/…records.jsonl`. Count
them and log the count.

## Engineering standards (locked)

* Raw data never changes. Everything downstream can be rebuilt from it.
* Every load is idempotent: rerunning any window gives the same result with no duplicates.
* Invalid records are quarantined and counted, **never silently dropped**.
* Timestamps are stored in UTC. Convert to `Europe/Madrid` only in marts, with a test covering
daylight-saving days.
* Data quality is checked at ingestion (Pydantic) and in the warehouse (dbt tests, source
freshness, contracts).
* Tests never call the live feed or the cloud. Use fixture files and local temporary folders.

## Repository layout (top level is locked)

```
README.md  CLAUDE.md  docs/adr/  docs/  ingestion/  dbt/  airflow/  setup/  tests/
.github/workflows/  docker-compose.yml  Makefile  pyproject.toml  .pre-commit-config.yaml  .env.example
```

Don't create other top-level folders without asking.

## Environment

* Development runs inside **WSL2 Ubuntu** (ADR-0005). Use Linux paths and LF line endings.
* The `Makefile` is the single entry point for common commands. Keep its targets short and
documented with `make help`.

## Open decisions (don't assume them)

* **Airflow setup, load format, Snowflake authentication, how only new files are loaded:** day 2.
* **Business questions, model grain, incremental and snapshot strategy:** day 3.
* **CI fixture design:** day 4.
