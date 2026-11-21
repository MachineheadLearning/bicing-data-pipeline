import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    """Retries must not slow the tests down."""
    monkeypatch.setattr("ingestion.client.sleep", lambda seconds: None)


@pytest.fixture
def fixture_bytes() -> Callable[[str], bytes]:
    """Return the exact bytes of a file in tests/fixtures/."""
    return lambda name: (FIXTURES_DIR / name).read_bytes()


@pytest.fixture
def fixture_json() -> Callable[[str], dict[str, Any]]:
    """Return a fixture parsed as JSON, so a test can change it before use."""
    return lambda name: json.loads((FIXTURES_DIR / name).read_bytes())
