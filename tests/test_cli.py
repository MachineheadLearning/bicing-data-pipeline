import argparse
import gzip
from collections.abc import Callable
from pathlib import Path

import httpx
import pytest

from ingestion.__main__ import main, parse_feeds

DISCOVERY_URL = "https://example.test/gbfs.json"


@pytest.fixture(autouse=True)
def env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("GBFS_DISCOVERY_URL", DISCOVERY_URL)
    monkeypatch.setenv("LOCAL_DATA_DIR", str(tmp_path / "data"))


def make_transport(
    fixture_bytes: Callable[[str], bytes], broken: dict[str, httpx.Response] | None = None
) -> httpx.MockTransport:
    """Serve the fixtures. `broken` maps a feed name to the response to give instead."""
    broken = broken or {}

    def handler(request: httpx.Request) -> httpx.Response:
        name = request.url.path.removesuffix(".json").rsplit("/", 1)[-1]
        if name in broken:
            return broken[name]
        return httpx.Response(200, content=fixture_bytes(f"{name}.json"))

    return httpx.MockTransport(handler)


def test_parse_feeds_splits_strips_and_removes_duplicates() -> None:
    assert parse_feeds("station_status, station_information,station_status") == [
        "station_status",
        "station_information",
    ]


@pytest.mark.parametrize("value", ["nope", "station_status,nope", " , "])
def test_parse_feeds_rejects_unknown_or_empty(value: str) -> None:
    with pytest.raises(argparse.ArgumentTypeError):
        parse_feeds(value)


def test_default_feed_is_station_status(
    tmp_path: Path, fixture_bytes: Callable[[str], bytes]
) -> None:
    assert main([], transport=make_transport(fixture_bytes)) == 0
    assert [p.name for p in (tmp_path / "data/raw/gbfs").iterdir()] == ["feed=station_status"]


def test_several_feeds_exit_0_and_write_files(
    tmp_path: Path, fixture_bytes: Callable[[str], bytes]
) -> None:
    code = main(
        ["--feeds", "station_status,station_information,vehicle_types"],
        transport=make_transport(fixture_bytes),
    )

    assert code == 0
    raw = tmp_path / "data/raw/gbfs"
    assert sorted(p.name for p in raw.iterdir()) == [
        "feed=station_information",
        "feed=station_status",
        "feed=vehicle_types",
    ]
    (status_file,) = (raw / "feed=station_status").rglob("*.json.gz")
    assert gzip.decompress(status_file.read_bytes()) == fixture_bytes("station_status.json")


def test_running_twice_is_safe(tmp_path: Path, fixture_bytes: Callable[[str], bytes]) -> None:
    transport = make_transport(fixture_bytes)
    assert main([], transport=transport) == 0
    assert main([], transport=transport) == 0
    assert len(list((tmp_path / "data").rglob("*.json.gz"))) == 1


def test_quarantined_payload_still_exits_0(
    tmp_path: Path, fixture_bytes: Callable[[str], bytes]
) -> None:
    transport = make_transport(
        fixture_bytes, broken={"station_status": httpx.Response(200, content=b"not json")}
    )

    assert main([], transport=transport) == 0
    assert not (tmp_path / "data/raw").exists()
    assert len(list((tmp_path / "data/quarantine").rglob("*.payload.json.gz"))) == 1


def test_exit_1_when_a_feed_cannot_be_fetched_but_other_feeds_are_still_written(
    tmp_path: Path, fixture_bytes: Callable[[str], bytes]
) -> None:
    transport = make_transport(fixture_bytes, broken={"station_status": httpx.Response(503)})

    code = main(["--feeds", "station_status,vehicle_types"], transport=transport)

    assert code == 1
    written = [p.name for p in (tmp_path / "data").rglob("*.json.gz")]
    assert len(written) == 1
    assert written[0].startswith("vehicle_types_")


def test_exit_1_when_discovery_fails(fixture_bytes: Callable[[str], bytes]) -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(404))
    assert main([], transport=transport) == 1


def test_unknown_feed_exits_2_without_any_request(capsys: pytest.CaptureFixture[str]) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("no request expected")

    with pytest.raises(SystemExit) as exit_info:
        main(["--feeds", "bogus"], transport=httpx.MockTransport(handler))

    assert exit_info.value.code == 2
    assert "unknown feed(s): bogus" in capsys.readouterr().err


def test_help_exits_0(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["--help"])
    assert exit_info.value.code == 0
    assert "--feeds" in capsys.readouterr().out
