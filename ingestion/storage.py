"""Where raw and quarantine files are written. Local folder only for now (S3 comes later)."""

import os
from pathlib import Path
from typing import Protocol


class Storage(Protocol):
    def write_once(self, key: str, content: bytes) -> bool:
        """Write `content` under `key`. Return False, and change nothing, if the key exists."""
        ...


class LocalStorage:
    """Stores keys as files below a root folder, so `data/` mirrors the bucket layout."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def write_once(self, key: str, content: bytes) -> bool:
        path = self.root / key
        path.parent.mkdir(parents=True, exist_ok=True)

        # Write to a temp file first, so a crash never leaves a half-written file at `path`.
        temp_path = path.parent / f".{path.name}.{os.getpid()}.tmp"
        temp_path.write_bytes(content)
        try:
            # A hard link appears at `path` in one step and fails if `path` already exists,
            # so an existing file can never be overwritten, even by a concurrent writer.
            os.link(temp_path, path)
        except FileExistsError:
            return False
        finally:
            temp_path.unlink(missing_ok=True)
        return True
