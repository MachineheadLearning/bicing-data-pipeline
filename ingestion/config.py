"""Settings read from environment variables, with defaults."""

import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_DISCOVERY_URL = "https://barcelona.publicbikesystem.net/customer/gbfs/v3.0/gbfs.json"
DEFAULT_DATA_DIR = "data"


@dataclass(frozen=True)
class Settings:
    discovery_url: str
    data_dir: Path


def load_settings() -> Settings:
    """Read GBFS_DISCOVERY_URL and LOCAL_DATA_DIR. An unset or empty variable uses its default."""
    return Settings(
        discovery_url=os.environ.get("GBFS_DISCOVERY_URL") or DEFAULT_DISCOVERY_URL,
        data_dir=Path(os.environ.get("LOCAL_DATA_DIR") or DEFAULT_DATA_DIR),
    )
