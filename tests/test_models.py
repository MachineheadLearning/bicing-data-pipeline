from collections.abc import Callable
from datetime import UTC
from typing import Any

import pytest
from pydantic import ValidationError

from ingestion.models import Envelope, StationInformation, StationStatus, VehicleType


def test_fixture_records_are_valid(fixture_json: Callable[[str], dict[str, Any]]) -> None:
    for station in fixture_json("station_status.json")["data"]["stations"]:
        StationStatus.model_validate(station)
    for station in fixture_json("station_information.json")["data"]["stations"]:
        StationInformation.model_validate(station)
    for vehicle_type in fixture_json("vehicle_types.json")["data"]["vehicle_types"]:
        VehicleType.model_validate(vehicle_type)


def test_station_without_post_code_is_valid(
    fixture_json: Callable[[str], dict[str, Any]],
) -> None:
    station = fixture_json("station_information.json")["data"]["stations"][2]
    assert "post_code" not in station
    assert StationInformation.model_validate(station).post_code is None


def test_extra_fields_are_allowed(fixture_json: Callable[[str], dict[str, Any]]) -> None:
    station = fixture_json("station_status.json")["data"]["stations"][0]
    station["brand_new_field"] = 1
    assert StationStatus.model_validate(station).model_extra == {"brand_new_field": 1}


@pytest.mark.parametrize(
    ("last_updated", "expected_utc"),
    [
        ("2026-11-14T23:02:04Z", "2026-11-14T23:02:04+00:00"),
        ("2026-11-14T22:59:47.557Z", "2026-11-14T22:59:47.557000+00:00"),
        ("2026-11-15T00:02:04+01:00", "2026-11-14T23:02:04+00:00"),
    ],
)
def test_envelope_parses_last_updated_with_and_without_milliseconds(
    last_updated: str, expected_utc: str
) -> None:
    envelope = Envelope.model_validate(
        {"version": "3.0", "ttl": 0, "last_updated": last_updated, "data": {}}
    )
    assert envelope.last_updated.astimezone(UTC).isoformat() == expected_utc


def test_envelope_rejects_a_last_updated_without_timezone() -> None:
    with pytest.raises(ValidationError):
        Envelope.model_validate(
            {"version": "3.0", "ttl": 0, "last_updated": "2026-11-14T23:02:04", "data": {}}
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("station_id", ""),
        ("num_vehicles_available", -1),
        ("num_docks_available", -1),
        ("is_renting", "maybe"),
        ("last_reported", "2026-11-14T22:59:47"),
        ("vehicle_types_available", [{"vehicle_type_id": "FIT", "count": -1}]),
    ],
)
def test_station_status_rejects_bad_values(
    fixture_json: Callable[[str], dict[str, Any]], field: str, value: object
) -> None:
    station = fixture_json("station_status.json")["data"]["stations"][0]
    station[field] = value
    with pytest.raises(ValidationError):
        StationStatus.model_validate(station)


@pytest.mark.parametrize(
    ("field", "value"),
    [("lat", 91), ("lon", -181), ("name", []), ("capacity", -5), ("station_id", "")],
)
def test_station_information_rejects_bad_values(
    fixture_json: Callable[[str], dict[str, Any]], field: str, value: object
) -> None:
    station = fixture_json("station_information.json")["data"]["stations"][0]
    station[field] = value
    with pytest.raises(ValidationError):
        StationInformation.model_validate(station)


def test_vehicle_type_rejects_negative_range(
    fixture_json: Callable[[str], dict[str, Any]],
) -> None:
    vehicle_type = fixture_json("vehicle_types.json")["data"]["vehicle_types"][0]
    vehicle_type["max_range_meters"] = -1.0
    with pytest.raises(ValidationError):
        VehicleType.model_validate(vehicle_type)
