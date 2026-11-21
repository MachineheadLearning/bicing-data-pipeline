# ADR-0002: Snapshot interval — 5 minutes

- **Status:** Accepted
- **Date:** 2026-11-15

## Context

The official feed (ADR-0001) publishes `ttl: 0` and `cache-control: max-age=0`, so it gives no
refresh cadence. Polling showed `last_updated` advancing on every request, and each station sends
a new `last_reported` about every 3 minutes on average. GBFS requires status data to be no more
than 5 minutes out of date. The feed returns no ETag, so every poll downloads the full
`station_status` payload (about 268 KB raw, about 10 KB gzipped, 544 stations).

## Options considered

- **5 minutes:** 288 snapshots a day, about 157k status rows a day, about 77 MB raw (about 3 MB
  gzipped) of `station_status` a day.
- **10 minutes:** half of each figure. Episodes when a station is empty or full and lasts under
  10 minutes are missed, which makes "time empty or full" metrics too low.

## Decision

Snapshot `station_status` every **5 minutes**.

## Consequences

- The sampling matches the feed's update rhythm and the GBFS 5-minute freshness target, so
  metrics about empty and full stations are meaningful.
- Raw storage stays small (S3 cost is cents per month either way).
- Warehouse cost depends on how often load and dbt run, not on how often we fetch. Because the
  locked architecture runs ingest, load and dbt on every schedule, a 5-minute schedule would wake
  the Snowflake warehouse 288 times a day. Whether to run load and dbt on a slower schedule is
  raised as a separate ADR on day 2.
- How often `station_information` (about 526 KB raw) is fetched is decided with the raw file
  layout. It is not tied to this interval.
- Source freshness thresholds (day 3/4) are set relative to the 5-minute interval, with
  tolerance for gaps when the host machine is off.
