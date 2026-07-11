"""CLI entrypoint for the ingestion Cloud Run Job.

Runs a full ingestion cycle to completion and exits non-zero on failure so the
Cloud Run Job (and Scheduler) records the run as failed. Also used locally via
``just ingest`` / ``uv run ingest-monarch``.
"""

from __future__ import annotations

import asyncio
import sys

from dl_common import get_logger

from dl_ingest.pipeline import run_ingestion

log = get_logger(__name__)


def main() -> None:
    try:
        counts = asyncio.run(run_ingestion())
        log.info("ingestion_done", counts=counts)
    except Exception:
        log.exception("ingestion_failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
