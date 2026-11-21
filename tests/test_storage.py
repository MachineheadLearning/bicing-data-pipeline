from pathlib import Path

from ingestion.storage import LocalStorage

KEY = "raw/gbfs/feed=station_status/dt=2026-11-14/station_status_20261114T230204Z.json.gz"


def test_write_once_creates_the_file_and_its_folders(tmp_path: Path) -> None:
    assert LocalStorage(tmp_path).write_once(KEY, b"first") is True
    assert (tmp_path / KEY).read_bytes() == b"first"


def test_write_once_never_overwrites(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path)
    storage.write_once(KEY, b"first")
    assert storage.write_once(KEY, b"second") is False
    assert (tmp_path / KEY).read_bytes() == b"first"


def test_write_once_leaves_no_temp_files(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path)
    storage.write_once(KEY, b"first")
    storage.write_once(KEY, b"second")  # skipped write must clean up too
    assert [p.name for p in (tmp_path / KEY).parent.iterdir()] == [Path(KEY).name]
