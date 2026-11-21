# ADR-0001: Data source — official Bicing GBFS 3.0 feed

- **Status:** Accepted
- **Date:** 2026-11-15

## Context

The pipeline needs one live source of Barcelona Bicing station data. Two candidates exist:
the operator's official GBFS feed and the CityBikes community mirror.

A hands-on check of the official feed on 2026-11-14 (13 polls of `station_status`, 15 s apart) found:

- **Reachable and fast.** Auto-discovery URL
  `https://barcelona.publicbikesystem.net/customer/gbfs/v3.0/gbfs.json`; GBFS 3.0. Every request
  returned HTTP 200 in 0.1–0.4 s. No authentication and no rate-limit headers.
- **Fresh.** `ttl` is 0 and `cache-control: max-age=0`, so the publisher gives no refresh cadence.
  `last_updated` advanced on every poll. 35–73 stations sent a new `last_reported` per 15 s window,
  about every 3 minutes per station on average (measured around midnight).
- **Complete.** 544 stations. All status fields are present, including the per-vehicle-type
  breakdown (`vehicle_types_available`). `vehicle_types` lists 10 types, each with a
  `propulsion_type`. `station_information.cross_street` carries district and neighbourhood.
- **Sizes.** `station_status` is about 268 KB raw (about 10 KB gzipped). `station_information` is
  about 526 KB raw (about 46 KB gzipped). No ETag, so every poll downloads the full payload.
- **License.** `system_information` has no `license_id`, `license_url` or `terms_url`. Under the
  GBFS 3.0 spec, an omitted license means the feed is provided under CC0 1.0 (Creative Commons
  Universal Public Domain Dedication). Contact: `mobility-data-client@lyft.com`.

The CityBikes mirror (`https://api.citybik.es/gbfs/2/bicing/gbfs.json`) publishes GBFS 2.3. It
uses integer POSIX timestamps where GBFS 3.0 uses RFC3339 strings, reports `ttl` 0, and is a
third party between us and the operator.

## Options considered

- **A. Official GBFS 3.0 feed only.**
- **B. CityBikes GBFS 2.3 mirror.** An older spec, an extra party in the chain, no confirmed
  per-station vehicle-type breakdown.
- **C. Official feed, with the mirror documented as an emergency fallback but not implemented.**

## Decision

**C.** Ingest from the official GBFS 3.0 feed. The CityBikes mirror is recorded here as a fallback
only. No code supports it.

## Consequences

- Pydantic models target GBFS 3.0 only: RFC3339 timestamps (with and without milliseconds),
  localized-string arrays for names, and optional `post_code` (missing on 3 stations).
- Switching to the mirror would need new models for GBFS 2.3 and a new ADR. Only do it if the
  official feed is unusable for a sustained period.
- Outages and schema changes in the official feed show up through quarantine counts and dbt
  source freshness checks. There is no automatic failover.
- The README credits the source (Bicing GBFS, CC0) as a courtesy, even though CC0 does not
  require it.
- With no ETag, every poll downloads the full payload. Polling frequency directly drives storage
  volume (see ADR-0002, snapshot interval).
