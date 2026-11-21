"""Pydantic models for the GBFS 3.0 documents we ingest (ADR-0001).

All models allow extra fields: the feed may add fields without breaking ingestion.
"""

from dataclasses import dataclass
from typing import Annotated, Any

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

NonEmptyStr = Annotated[str, Field(min_length=1)]
NonNegativeInt = Annotated[int, Field(ge=0)]
NonNegativeFloat = Annotated[float, Field(ge=0)]


class GbfsModel(BaseModel):
    model_config = ConfigDict(extra="allow")


# --- Envelope (top level of every feed) ---


class PayloadTimestamp(GbfsModel):
    """Only `last_updated`. Used to name a quarantined payload when the rest of it is invalid."""

    last_updated: AwareDatetime


class Envelope(PayloadTimestamp):
    version: str
    ttl: NonNegativeInt
    data: dict[str, Any]


# --- Records ---


class LocalizedText(GbfsModel):
    text: str
    language: str


class VehicleTypeCount(GbfsModel):
    vehicle_type_id: str
    count: NonNegativeInt


class VehicleDocksCount(GbfsModel):
    vehicle_type_ids: list[str]
    count: NonNegativeInt


class StationStatus(GbfsModel):
    station_id: NonEmptyStr
    num_vehicles_available: NonNegativeInt
    num_docks_available: NonNegativeInt | None = None
    num_vehicles_disabled: NonNegativeInt | None = None
    num_docks_disabled: NonNegativeInt | None = None
    is_installed: bool
    is_renting: bool
    is_returning: bool
    last_reported: AwareDatetime
    vehicle_types_available: list[VehicleTypeCount] | None = None
    vehicle_docks_available: list[VehicleDocksCount] | None = None


class StationInformation(GbfsModel):
    station_id: NonEmptyStr
    name: Annotated[list[LocalizedText], Field(min_length=1)]
    lat: Annotated[float, Field(ge=-90, le=90)]
    lon: Annotated[float, Field(ge=-180, le=180)]
    capacity: NonNegativeInt | None = None
    address: str | None = None
    cross_street: str | None = None
    post_code: str | None = None
    is_charging_station: bool | None = None
    is_virtual_station: bool | None = None


class VehicleType(GbfsModel):
    vehicle_type_id: NonEmptyStr
    form_factor: str
    propulsion_type: str
    max_range_meters: NonNegativeFloat | None = None
    name: list[LocalizedText]


# --- Discovery document (gbfs.json) ---


class DiscoveryFeed(GbfsModel):
    name: str
    url: str


class DiscoveryData(GbfsModel):
    feeds: list[DiscoveryFeed]


class Discovery(GbfsModel):
    data: DiscoveryData


# --- Supported feeds ---


@dataclass(frozen=True)
class FeedSpec:
    """Where a feed keeps its records, and which model each record must satisfy."""

    records_key: str  # key inside the envelope's `data`
    record_model: type[GbfsModel]
    id_field: str  # copied into the quarantine file to find the bad record


FEEDS: dict[str, FeedSpec] = {
    "station_status": FeedSpec("stations", StationStatus, "station_id"),
    "station_information": FeedSpec("stations", StationInformation, "station_id"),
    "vehicle_types": FeedSpec("vehicle_types", VehicleType, "vehicle_type_id"),
}
