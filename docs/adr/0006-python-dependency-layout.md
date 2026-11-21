# ADR-0006: Python dependency layout — Airflow image separate, dbt in its own environment

- **Status:** Accepted
- **Date:** 2026-11-15

## Context

Latest stable releases on 2026-11-15 (PyPI): apache-airflow 3.4.0 (Python ≥3.11), dbt-core 1.12.7,
dbt-snowflake 1.12.5, dbt-duckdb 1.11.1, duckdb 2.0.0, pydantic 2.14.3. The project uses Python 3.12.

Airflow must be installed with its constraints file (exact, tested versions of every dependency).
A test resolution with `uv` showed:

- Airflow 3.4.0 plus dbt-core 1.12.7, dbt-snowflake and dbt-duckdb, **with** the Airflow 3.4.0
  constraints for Python 3.12: **fails**. dbt-core requires `pathspec<1.1`, while the constraints pin
  `pathspec==1.1.1`.
- The same set **without** the constraints file resolves, but Airflow then runs on versions it was
  not tested with.

Running dbt in a separate virtual environment from Airflow is the widely recommended practice
(Astronomer, and the dbt-core maintainers in issue #11222).

## Options considered

- **A.** One environment for everything, without Airflow's constraints file.
- **B.** Separate environments: Airflow plus ingestion in the official Airflow image, installed with
  its constraints file; dbt in its own virtual environment; one `uv` project for local development
  and CI, without Airflow.
- **C.** dbt in its own container, launched by Airflow.

## Decision

**B.**

- **Airflow image** (day 2): based on the official `apache/airflow:3.4.0` image for Python 3.12.
  Providers and the ingestion package's dependencies are installed with the Airflow 3.4.0 /
  Python 3.12 constraints file. dbt-core and its adapters are installed in a separate virtual
  environment inside the image, which the dbt task calls.
- **Local development and CI:** one `uv` project (`pyproject.toml` plus `uv.lock`, Python 3.12)
  with the ingestion code, dbt-core 1.12.x, dbt-snowflake, dbt-duckdb and the dev tools (ruff,
  pytest, pre-commit). Airflow is not installed in it.
- **Pinned versions at project start:** apache-airflow 3.4.0, dbt-core 1.12.7, dbt-snowflake
  1.12.5, dbt-duckdb 1.11.1. The exact versions of everything else are recorded in `uv.lock`.

## Consequences

- Airflow runs on its tested dependency set, and dbt can be upgraded independently.
- The ingestion package's dependencies must fit within Airflow's constraints. Claude Code must not
  add an ingestion dependency that conflicts with them.
- There are two dependency lists to keep aligned (`pyproject.toml` and the Airflow image's
  requirements). The dbt versions must match in both.
- CI never installs Airflow, so it stays fast. DAG-level tests that need Airflow are decided on
  day 2.
- DuckDB 2.0.0 is very new. The dbt-duckdb plus DuckDB 2.0 pairing is verified on day 4, with
  `duckdb<2` as the fallback pin.
- dbt v2 exists as a separate generation. The project stays on dbt-core 1.12 as locked (actively
  supported until 2027-07-15).
