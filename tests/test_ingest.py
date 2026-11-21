import gzip
import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ingestion.ingest import process_payload
from ingestion.storage import LocalStorage

FETCHED_AT = datetime(2026, 11, 15, 8, 30, 15, tzinfo=UTC)
RAW_KEY = "raw/gbfs/feed=station_status/dt=2026-11-14/station_status_20261114T230204Z.json.gz"
RECORDS_KEY = (
    "quarantine/gbfs/feed=station_status/dt=2026-11-14/"
    "station_status_20261114T230204Z.records.jsonl"
)


def files_under(root: Path) -> list[str]:
    return sorted(str(p.relative_to(root)) for p in root.rglob("*") if p.is_file())


def test_valid_payload_is_written_to_the_raw_key_unchanged(
    tmp_path: Path, fixture_bytes: Callable[[str], bytes]
) -> None:
    body = fixture_bytes("station_status.json")

    result = process_payload("station_status", body, FETCHED_AT, LocalStorage(tmp_path))

    assert files_under(tmp_path) == [RAW_KEY]
    assert gzip.decompress((tmp_path / RAW_KEY).read_bytes()) == body
    assert result.raw_key == RAW_KEY
    assert result.written is True
    assert result.last_updated == datetime(2026, 11, 14, 23, 2, 4, tzinfo=UTC)
    assert (result.records_total, result.records_valid, result.records_invalid) == (3, 3, 0)
    assert result.payload_quarantined is False


def test_raw_bytes_are_not_reserialised(
    tmp_path: Path, fixture_bytes: Callable[[str], bytes]
) -> None:
    # The fixture contains "Ó" and a trailing newline: json.dumps would escape the first
    # and drop the second, so equality proves the original bytes were stored.
    body = fixture_bytes("station_information.json")
    assert "Ó".encode() in body

    process_payload("station_information", body, FETCHED_AT, LocalStorage(tmp_path))

    key = (
        "raw/gbfs/feed=station_information/dt=2026-11-14/"
        "station_information_20261114T230000Z.json.gz"
    )
    assert gzip.decompress((tmp_path / key).read_bytes()) == body


def test_vehicle_types_payload_is_written(
    tmp_path: Path, fixture_bytes: Callable[[str], bytes]
) -> None:
    result = process_payload(
        "vehicle_types", fixture_bytes("vehicle_types.json"), FETCHED_AT, LocalStorage(tmp_path)
    )
    assert result.raw_key == (
        "raw/gbfs/feed=vehicle_types/dt=2026-11-14/vehicle_types_20261114T230000Z.json.gz"
    )
    assert (result.records_total, result.records_valid, result.records_invalid) == (2, 2, 0)


def test_gzip_output_is_deterministic(
    tmp_path: Path, fixture_bytes: Callable[[str], bytes]
) -> None:
    body = fixture_bytes("station_status.json")
    first = tmp_path / "first"
    second = tmp_path / "second"

    process_payload("station_status", body, FETCHED_AT, LocalStorage(first))
    process_payload("station_status", body, datetime(2030, 1, 1, tzinfo=UTC), LocalStorage(second))

    assert (first / RAW_KEY).read_bytes() == (second / RAW_KEY).read_bytes()


def test_rerun_with_the_same_payload_skips_the_write(
    tmp_path: Path, fixture_bytes: Callable[[str], bytes]
) -> None:
    body = fixture_bytes("station_status.json")
    storage = LocalStorage(tmp_path)

    first = process_payload("station_status", body, FETCHED_AT, storage)
    before = (tmp_path / RAW_KEY).stat().st_mtime_ns
    second = process_payload("station_status", body, FETCHED_AT, storage)

    assert (first.written, second.written) == (True, False)
    assert second.raw_key == RAW_KEY
    assert (tmp_path / RAW_KEY).stat().st_mtime_ns == before
    assert files_under(tmp_path) == [RAW_KEY]


def test_invalid_record_is_quarantined_and_payload_still_goes_to_raw(
    tmp_path: Path, fixture_json: Callable[[str], dict[str, Any]]
) -> None:
    payload = fixture_json("station_status.json")
    payload["data"]["stations"][1]["num_vehicles_available"] = -3
    body = json.dumps(payload).encode()

    result = process_payload("station_status", body, FETCHED_AT, LocalStorage(tmp_path))

    assert files_under(tmp_path) == sorted([RAW_KEY, RECORDS_KEY])
    assert gzip.decompress((tmp_path / RAW_KEY).read_bytes()) == body
    assert (result.records_total, result.records_valid, result.records_invalid) == (3, 2, 1)
    assert result.payload_quarantined is False

    lines = (tmp_path / RECORDS_KEY).read_text().splitlines()
    assert len(lines) == 1
    line = json.loads(lines[0])
    assert line["record_index"] == 1
    assert line["station_id"] == "2"
    assert line["record"] == payload["data"]["stations"][1]
    assert line["errors"][0]["loc"] == ["num_vehicles_available"]
    assert line["errors"][0]["type"] == "greater_than_equal"


def test_record_that_is_not_an_object_is_quarantined(tmp_path: Path) -> None:
    payload = {
        "version": "3.0",
        "ttl": 0,
        "last_updated": "2026-11-14T23:02:04Z",
        "data": {"stations": ["oops"]},
    }

    result = process_payload(
        "station_status", json.dumps(payload).encode(), FETCHED_AT, LocalStorage(tmp_path)
    )

    assert (result.records_total, result.records_valid, result.records_invalid) == (1, 0, 1)
    line = json.loads((tmp_path / RECORDS_KEY).read_text())
    assert "station_id" not in line
    assert line["record"] == "oops"


def test_non_json_body_is_quarantined_with_fetch_time_name(tmp_path: Path) -> None:
    body = b"<html>Service unavailable</html>"

    result = process_payload("station_status", body, FETCHED_AT, LocalStorage(tmp_path))

    key = (
        "quarantine/gbfs/feed=station_status/dt=2026-11-15/"
        "station_status_20261115T083015Z.payload.json.gz"
    )
    assert files_under(tmp_path) == [key]
    assert gzip.decompress((tmp_path / key).read_bytes()) == body
    assert result.payload_quarantined is True
    assert result.raw_key is None
    assert result.written is False
    assert result.last_updated is None


def test_envelope_missing_last_updated_is_quarantined_and_not_in_raw(
    tmp_path: Path, fixture_json: Callable[[str], dict[str, Any]]
) -> None:
    payload = fixture_json("station_status.json")
    del payload["last_updated"]

    result = process_payload(
        "station_status", json.dumps(payload).encode(), FETCHED_AT, LocalStorage(tmp_path)
    )

    assert result.payload_quarantined is True
    assert not (tmp_path / "raw").exists()
    assert files_under(tmp_path) == [
        "quarantine/gbfs/feed=station_status/dt=2026-11-15/"
        "station_status_20261115T083015Z.payload.json.gz"
    ]


def test_invalid_envelope_with_valid_last_updated_is_named_after_last_updated(
    tmp_path: Path, fixture_json: Callable[[str], dict[str, Any]]
) -> None:
    payload = fixture_json("station_status.json")
    del payload["version"]

    result = process_payload(
        "station_status", json.dumps(payload).encode(), FETCHED_AT, LocalStorage(tmp_path)
    )

    assert result.payload_quarantined is True
    assert result.last_updated == datetime(2026, 11, 14, 23, 2, 4, tzinfo=UTC)
    assert files_under(tmp_path) == [
        RAW_KEY.replace("raw/", "quarantine/").replace(".json.gz", ".payload.json.gz")
    ]


def test_payload_without_the_records_list_is_quarantined(tmp_path: Path) -> None:
    payload = {"version": "3.0", "ttl": 0, "last_updated": "2026-11-14T23:02:04Z", "data": {}}

    result = process_payload(
        "station_status", json.dumps(payload).encode(), FETCHED_AT, LocalStorage(tmp_path)
    )

    assert result.payload_quarantined is True
    assert not (tmp_path / "raw").exists()


def test_last_updated_with_and_without_milliseconds_and_with_offset_use_utc(
    tmp_path: Path, fixture_json: Callable[[str], dict[str, Any]]
) -> None:
    cases = {
        "2026-11-14T23:02:04Z": "dt=2026-11-14/station_status_20261114T230204Z",
        "2026-11-14T23:02:04.987Z": "dt=2026-11-14/station_status_20261114T230204Z",
        # 00:30 in Madrid (UTC+1) is still the previous day in UTC.
        "2026-11-15T00:30:00+01:00": "dt=2026-11-14/station_status_20261114T233000Z",
    }
    for last_updated, expected in cases.items():
        payload = fixture_json("station_status.json")
        payload["last_updated"] = last_updated
        storage = LocalStorage(tmp_path / last_updated)  # one folder per case

        result = process_payload(
            "station_status", json.dumps(payload).encode(), FETCHED_AT, storage
        )

        assert result.payload_quarantined is False
        assert result.raw_key == f"raw/gbfs/feed=station_status/{expected}.json.gz"
        assert result.last_updated is not None
        assert result.last_updated.tzinfo is UTC
