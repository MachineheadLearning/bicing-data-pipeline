import httpx
import pytest

from ingestion import client as client_module
from ingestion.client import MAX_ATTEMPTS, USER_AGENT, DiscoveryError, FetchError, GbfsClient

URL = "https://example.test/gbfs/station_status.json"
DISCOVERY_URL = "https://example.test/gbfs.json"


def make_client(handler: httpx.MockTransport) -> GbfsClient:
    return GbfsClient(transport=handler)


def test_retry_503_then_200_succeeds() -> None:
    responses = [httpx.Response(503), httpx.Response(200, content=b"ok")]
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return responses[len(calls) - 1]

    with make_client(httpx.MockTransport(handler)) as client:
        assert client.fetch(URL) == b"ok"
    assert len(calls) == 2


def test_persistent_5xx_fails_after_three_attempts() -> None:
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(500)

    with make_client(httpx.MockTransport(handler)) as client, pytest.raises(FetchError) as error:
        client.fetch(URL)
    assert len(calls) == MAX_ATTEMPTS == 3
    assert "after 3 attempts" in str(error.value)


def test_404_is_not_retried() -> None:
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(404)

    with make_client(httpx.MockTransport(handler)) as client, pytest.raises(FetchError):
        client.fetch(URL)
    assert len(calls) == 1


def test_timeouts_and_connection_errors_are_retried() -> None:
    errors: list[Exception] = [httpx.ConnectTimeout("slow"), httpx.ConnectError("refused")]
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        if errors:
            raise errors.pop(0)
        return httpx.Response(200, content=b"ok")

    with make_client(httpx.MockTransport(handler)) as client:
        assert client.fetch(URL) == b"ok"
    assert len(calls) == 3


def test_backoff_doubles_between_attempts(monkeypatch: pytest.MonkeyPatch) -> None:
    delays: list[float] = []
    monkeypatch.setattr(client_module, "sleep", delays.append)

    with (
        make_client(httpx.MockTransport(lambda request: httpx.Response(502))) as client,
        pytest.raises(FetchError),
    ):
        client.fetch(URL)
    assert delays == [1.0, 2.0]  # no wait after the last attempt


def test_requests_send_the_user_agent() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers["user-agent"])
        return httpx.Response(200, content=b"{}")

    with make_client(httpx.MockTransport(handler)) as client:
        client.fetch(URL)
    assert seen == [USER_AGENT]


def discovery_transport(fixture_bytes: bytes) -> httpx.MockTransport:
    return httpx.MockTransport(lambda request: httpx.Response(200, content=fixture_bytes))


def test_discovery_resolves_feed_urls(fixture_bytes) -> None:
    transport = discovery_transport(fixture_bytes("gbfs.json"))
    with make_client(transport) as client:
        urls = client.feed_urls(DISCOVERY_URL, ["station_status", "vehicle_types"])
    assert urls == {
        "station_status": "https://example.test/gbfs/station_status.json",
        "vehicle_types": "https://example.test/gbfs/vehicle_types.json",
    }


def test_unknown_feed_name_raises_a_clear_error_before_any_request() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("no request expected")

    with make_client(httpx.MockTransport(handler)) as client, pytest.raises(DiscoveryError) as e:
        client.feed_urls(DISCOVERY_URL, ["station_status", "free_bike_status"])
    assert "free_bike_status" in str(e.value)
    assert "Supported feeds" in str(e.value)


def test_feed_missing_from_the_discovery_document_raises() -> None:
    body = b'{"version": "3.0", "data": {"feeds": [{"name": "vehicle_types", "url": "u"}]}}'
    with (
        make_client(discovery_transport(body)) as client,
        pytest.raises(DiscoveryError, match="station_status"),
    ):
        client.feed_urls(DISCOVERY_URL, ["station_status"])


def test_invalid_discovery_document_raises() -> None:
    with (
        make_client(discovery_transport(b"not json")) as client,
        pytest.raises(DiscoveryError, match="Invalid discovery document"),
    ):
        client.feed_urls(DISCOVERY_URL, ["station_status"])
