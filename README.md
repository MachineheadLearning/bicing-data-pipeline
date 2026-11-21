# bicing-data-pipeline

Batch pipeline on live Barcelona Bicing GBFS data: Python, Airflow 3, dbt, Snowflake, S3, DuckDB.

Status: work in progress

## Development setup

On Windows, develop inside WSL2 Ubuntu (native Windows is not supported).

```bash
make install                  # install dependencies
make check                    # lint and tests
uv run pre-commit install     # run the checks before every commit
```
