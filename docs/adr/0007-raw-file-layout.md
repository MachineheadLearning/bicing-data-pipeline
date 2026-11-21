# ADR-0007: Raw file layout, naming and quarantine

* **Status:** Accepted
* **Date:** 2026-11-21

## Context

Raw payloads must be stored exactly as received and must never change. Loads must pick up only new
files, and reruns must not create duplicates. The same layout is used in the S3 bucket (cloud mode)
and in a local folder (local mode).

Feed facts (ADR-0001, ADR-0002):

* `station\_status` is about 268 KB raw (about 10 KB gzipped) and is polled every 5 minutes.
* `station\_information` is about 526 KB raw (about 46 KB gzipped).
* `vehicle\_types` is about 4 KB.
* `ttl` is 0 and there is no ETag, so every poll returns a fresh snapshot.
* Every feed carries its own `last\_updated` timestamp in RFC3339 UTC format.

## Options considered

1. **Folder structure:** `key=value` partition folders (`feed=<name>/dt=YYYY-MM-DD/`) or plain date
folders (`<feed>/YYYY/MM/DD/`).
2. **File name:** the feed's own `last\_updated`, or the scheduled run time.
3. **Compression:** gzip, or plain JSON.
4. **Fetch frequency per feed:** all feeds every 5 minutes, or `station\_status` every 5 minutes and
the reference feeds hourly.
5. **Invalid data:** quarantine the bad parts and keep the rest, or reject whole payloads. - A payload

&#x20;  whose envelope is valid but whose records list (`data.stations` or `data.vehicle\_types`) is

&#x20;  missing or not a list is treated as a top-level failure and quarantined, so it never loads

&#x20;  as an empty snapshot.

## Decision

1. **Folder structure:** `key=value` partition folders by feed and UTC date.
2. **File name:** the feed's own `last\_updated`, in UTC, formatted `YYYYMMDDTHHMMSSZ`.
3. **Compression:** the payload bytes are gzipped unchanged. Decompressing gives back exactly the
bytes received.
4. **Fetch frequency:** `station\_status` every 5 minutes. `station\_information` and
`vehicle\_types` every hour.
5. **Invalid data:**

   * A payload that fails top-level GBFS validation (not JSON, or missing required top-level
fields) is written to `quarantine/` instead of `raw/` and is never loaded.
   * Inside a valid payload, station records that fail validation are written with their error
reason to `quarantine/` as JSON lines and counted. The full payload still goes to `raw/`
unchanged, and staging excludes the invalid records. This record-level rule is required by
the locked scope ("invalid records go to a quarantine area and are counted").

Layout. The local `data/` folder (git-ignored) mirrors the bucket exactly:

```
raw/gbfs/feed=station\_status/dt=2026-11-15/station\_status\_20261115T140211Z.json.gz
raw/gbfs/feed=station\_information/dt=2026-11-15/station\_information\_20261115T140000Z.json.gz
raw/gbfs/feed=vehicle\_types/dt=2026-11-15/vehicle\_types\_20261115T140000Z.json.gz
quarantine/gbfs/feed=station\_status/dt=2026-11-15/station\_status\_20261115T140211Z.payload.json.gz
quarantine/gbfs/feed=station\_status/dt=2026-11-15/station\_status\_20261115T140211Z.records.jsonl
```

* `dt` is the UTC date of `last\_updated`.
* **Write-once rule:** a file is never overwritten. If the target name already exists, the write
is skipped and logged. The same name means the same snapshot, so reruns are safe.
* If `last\_updated` is missing or can't be parsed, the payload is quarantined and its file name
uses the fetch time in UTC instead.

## Consequences

* **Idempotency is defined by the file name.** "Rerunning a time window" means reloading and
remodelling from the raw files for that window. Fetching again can't reproduce the past, because
the feed is live.
* **Partition reads.** Snowflake (`PATTERN` on the path) and DuckDB (`hive\_partitioning`) can both
read a feed or a single day directly from the path.
* **Size.** Gzip cuts storage about 25 times, and Snowflake and DuckDB both read `.gz` directly.
* **Two fetch schedules.** The ingestion code takes the list of feeds to fetch as a parameter. How
Airflow runs the two schedules is decided on day 2.
* **New stations.** A brand-new station can appear in `station\_status` up to an hour before it
appears in `station\_information`. Staging and the tests that link the two tables must handle
that gap; this is decided on day 3.
* **No S3 versioning needed.** Immutability comes from the write-once rule. On day 2 we check
whether S3 conditional writes (`If-None-Match`) can enforce it in the bucket itself.
