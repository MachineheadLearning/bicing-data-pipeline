"""Command line entry point: python -m ingestion --feeds station_status,station_information"""

import argparse
import logging
from collections.abc import Sequence

import httpx

from ingestion.client import DiscoveryError, FetchError, GbfsClient
from ingestion.config import load_settings
from ingestion.ingest import ingest_feeds
from ingestion.models import FEEDS
from ingestion.storage import LocalStorage

logger = logging.getLogger(__name__)


def parse_feeds(value: str) -> list[str]:
    """Turn 'a,b' into ['a', 'b'] and reject names we do not support."""
    feeds = list(dict.fromkeys(name.strip() for name in value.split(",") if name.strip()))
    if not feeds:
        raise argparse.ArgumentTypeError("no feed given")
    unknown = [feed for feed in feeds if feed not in FEEDS]
    if unknown:
        raise argparse.ArgumentTypeError(
            f"unknown feed(s): {', '.join(unknown)}. Supported feeds: {', '.join(FEEDS)}"
        )
    return feeds


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m ingestion",
        description="Fetch GBFS feeds, validate them and write raw files to the local data folder.",
        epilog="Environment: GBFS_DISCOVERY_URL, LOCAL_DATA_DIR (see .env.example).",
    )
    parser.add_argument(
        "--feeds",
        type=parse_feeds,
        default="station_status",  # argparse runs the default through parse_feeds too
        help=f"comma-separated feeds (default: station_status). Choices: {', '.join(FEEDS)}",
    )
    return parser


def main(argv: Sequence[str] | None = None, transport: httpx.BaseTransport | None = None) -> int:
    """Return 0 on success (quarantined data included), 1 if a feed could not be fetched."""
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    settings = load_settings()

    try:
        with GbfsClient(transport=transport) as client:
            run = ingest_feeds(
                args.feeds, settings.discovery_url, client, LocalStorage(settings.data_dir)
            )
    except (FetchError, DiscoveryError) as exc:
        logger.error("%s", exc)
        return 1
    return 1 if run.failed_feeds else 0


if __name__ == "__main__":
    raise SystemExit(main())
