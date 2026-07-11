"""CLI entrypoint for the splitter Cloud Run Job.

Dry-run behavior comes from the SPLIT_DRY_RUN setting (default true). The
justfile exposes `just split-dry` and `just split`.
"""

from __future__ import annotations

import asyncio
import sys

from dl_common import get_logger

from dl_splitter.pipeline import run_splitter

log = get_logger(__name__)


def main() -> None:
    try:
        result = asyncio.run(run_splitter())
        log.info("splitter_done", dry_run=result["dry_run"], count=result["count"])
    except Exception:
        log.exception("splitter_failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
