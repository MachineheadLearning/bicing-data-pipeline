"""Fetch feeds, validate them, and write raw and quarantine files (ADR-0007)."""

import gzip
import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from pydantic import ValidationError

from ingestion.client import FetchError, GbfsClient
from ingestion.models import FEEDS, Envelope, FeedSpec, PayloadTimestamp
from ingestion.storage import Storage

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FeedResult:
    """What happened to one feed in one run."""

    feed: str
    last_updated: datetime | None  # UTC; None if the payload had no usable last_updated
    raw_key: str | None  # None if the payload was quarantined
    written: bool  # False if the raw file already existed, or the payload was quarantined
    records_total: int
    records_valid: int
    records_invalid: int
    payload_quarantined: bool


@dataclass(frozen=True)
class RunResult:
    results: list[FeedResult]
    failed_feeds: list[str]  # feeds that could not be fetched


def build_key(area: str, feed: str, timestamp: datetime, suffix: str) -> str:
    """Build a key like raw/gbfs/feed=<feed>/dt=YYYY-MM-DD/<feed>_YYYYMMDDTHHMMSSZ.<suffix>."""
    utc = timestamp.astimezone(UTC)
    return f"{area}/gbfs/feed={feed}/dt={utc:%Y-%m-%d}/{feed}_{utc:%Y%m%dT%H%M%SZ}.{suffix}"


def process_payload(feed: str, body: bytes, fetched_at: datetime, storage: Storage) -> FeedResult:
    """Validate one fetched payload and write it to raw/ or quarantine/."""
    spec = FEEDS[feed]
    compressed = gzip.compress(body, mtime=0)  # mtime=0: same input always gives the same bytes

    try:
        envelope = Envelope.model_validate_json(body)
    except ValidationError as exc:
        return _quarantine_payload(feed, body, compressed, fetched_at, storage, str(exc))

    records = envelope.data.get(spec.records_key)
    if not isinstance(records, list):
        reason = f"data.{spec.records_key} is missing or is not a list"
        return _quarantine_payload(feed, body, compressed, fetched_at, storage, reason)

    last_updated = envelope.last_updated.astimezone(UTC)
    raw_key = build_key("raw", feed, last_updated, "json.gz")
    written = storage.write_once(raw_key, compressed)
    if not written:
        logger.info("Skipped %s: already exists", raw_key)

    valid_count, invalid_lines = _validate_records(spec, records)
    if invalid_lines:
        records_key = build_key("quarantine", feed, last_updated, "records.jsonl")
        storage.write_once(records_key, "".join(invalid_lines).encode("utf-8"))
        logger.warning("%s: %d invalid record(s) quarantined", feed, len(invalid_lines))

    return FeedResult(
        feed=feed,
        last_updated=last_updated,
        raw_key=raw_key,
        written=written,
        records_total=len(records),
        records_valid=valid_count,
        records_invalid=len(invalid_lines),
        payload_quarantined=False,
    )


def _quarantine_payload(
    feed: str, body: bytes, compressed: bytes, fetched_at: datetime, storage: Storage, reason: str
) -> FeedResult:
    """Write the payload to quarantine/ only. Name it by last_updated, else by fetch time."""
    try:
        last_updated = PayloadTimestamp.model_validate_json(body).last_updated.astimezone(UTC)
    except ValidationError:
        last_updated = None

    key = build_key("quarantine", feed, last_updated or fetched_at, "payload.json.gz")
    if not storage.write_once(key, compressed):
        logger.info("Skipped %s: already exists", key)
    logger.warning("%s: payload quarantined as %s. Reason: %s", feed, key, reason)

    return FeedResult(
        feed=feed,
        last_updated=last_updated,
        raw_key=None,
        written=False,
        records_total=0,
        records_valid=0,
        records_invalid=0,
        payload_quarantined=True,
    )


def _validate_records(spec: FeedSpec, records: list[Any]) -> tuple[int, list[str]]:
    """Return the number of valid records and one JSON line for each invalid record."""
    invalid_lines: list[str] = []
    for index, record in enumerate(records):
        try:
            spec.record_model.model_validate(record)
        except ValidationError as exc:
            line: dict[str, Any] = {"record_index": index}
            if isinstance(record, dict) and spec.id_field in record:
                line[spec.id_field] = record[spec.id_field]
            line["errors"] = json.loads(exc.json(include_url=False))  # JSON-safe error list
            line["record"] = record
            invalid_lines.append(json.dumps(line, ensure_ascii=False) + "\n")
    return len(records) - len(invalid_lines), invalid_lines


def ingest_feeds(
    feeds: list[str], discovery_url: str, client: GbfsClient, storage: Storage
) -> RunResult:
    """Fetch the feeds one after the other. A feed that cannot be fetched does not stop the rest."""
    urls = client.feed_urls(discovery_url, feeds)
    results: list[FeedResult] = []
    failed_feeds: list[str] = []

    for feed in feeds:
        try:
            body = client.fetch(urls[feed])
        except FetchError as exc:
            logger.error("%s: %s", feed, exc)
            failed_feeds.append(feed)
            continue
        result = process_payload(feed, body, datetime.now(UTC), storage)
        logger.info("%s", result)
        results.append(result)

    return RunResult(results=results, failed_feeds=failed_feeds)
