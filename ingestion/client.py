"""HTTP access to the GBFS feed: fetch with retries, and discovery of feed URLs."""

import logging
from time import sleep
from types import TracebackType

import httpx
from pydantic import ValidationError

from ingestion.models import FEEDS, Discovery

logger = logging.getLogger(__name__)

USER_AGENT = (
    "bicing-data-pipeline/0.1 (+https://github.com/MachineheadLearning/bicing-data-pipeline)"
)
TIMEOUT_SECONDS = 10.0
MAX_ATTEMPTS = 3
BACKOFF_SECONDS = 1.0  # wait 1 s after the first failed attempt, 2 s after the second


class FetchError(Exception):
    """A URL could not be fetched (retries exhausted, or a non-retryable HTTP status)."""


class DiscoveryError(Exception):
    """The requested feeds are unknown, or the discovery document is unusable."""


class GbfsClient:
    def __init__(self, transport: httpx.BaseTransport | None = None) -> None:
        # `transport` lets tests plug in httpx.MockTransport instead of the network.
        self._client = httpx.Client(
            timeout=TIMEOUT_SECONDS,
            headers={"User-Agent": USER_AGENT},
            transport=transport,
        )

    def __enter__(self) -> "GbfsClient":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self._client.close()

    def fetch(self, url: str) -> bytes:
        """GET `url` and return the body. Retry only network errors, timeouts and HTTP 5xx."""
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                response = self._client.get(url)
            except httpx.TransportError as exc:
                reason = f"{type(exc).__name__}: {exc}"
            else:
                if response.is_success:
                    return response.content
                reason = f"HTTP {response.status_code}"
                if response.status_code < 500:
                    raise FetchError(f"GET {url} failed, not retrying: {reason}")

            if attempt < MAX_ATTEMPTS:
                delay = BACKOFF_SECONDS * 2 ** (attempt - 1)
                logger.warning(
                    "GET %s failed (%s), attempt %d/%d", url, reason, attempt, MAX_ATTEMPTS
                )
                sleep(delay)
        raise FetchError(f"GET {url} failed after {MAX_ATTEMPTS} attempts: {reason}")

    def feed_urls(self, discovery_url: str, feeds: list[str]) -> dict[str, str]:
        """Read the discovery document and return the URL of each requested feed."""
        unknown = [feed for feed in feeds if feed not in FEEDS]
        if unknown:
            raise DiscoveryError(f"Unknown feed(s) {unknown}. Supported feeds: {list(FEEDS)}")

        try:
            discovery = Discovery.model_validate_json(self.fetch(discovery_url))
        except ValidationError as exc:
            raise DiscoveryError(f"Invalid discovery document at {discovery_url}: {exc}") from exc

        available = {feed.name: feed.url for feed in discovery.data.feeds}
        missing = [feed for feed in feeds if feed not in available]
        if missing:
            raise DiscoveryError(f"Feed(s) {missing} not listed in {discovery_url}")
        return {feed: available[feed] for feed in feeds}
