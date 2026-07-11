"""Ingestion pipeline: full pull from Monarch -> MERGE-upsert into monarch.*.

Each entity is pulled in full and upserted with soft-delete detection, so the
source layer stays one-row-per-record while still capturing deletions. Budgets
are stored as a single non-deleting snapshot because they are not per-id records.

This pipeline owns its dataset name and creates the dataset on first run.
"""

from __future__ import annotations

from typing import Any

from dl_common import BigQueryClient, get_logger, get_settings
from dl_monarch import MonarchClient

log = get_logger(__name__)

# This ingestion's BigQuery dataset. The pipeline dictates + creates it.
DATASET = "monarch"


async def run_ingestion(lookback_days: int | None = None) -> dict[str, int]:
    """Run a full ingestion cycle and return per-entity row counts."""
    settings = get_settings()
    bq = BigQueryClient(dataset=DATASET)
    bq.ensure_dataset(DATASET)
    monarch = MonarchClient()
    await monarch.login()

    counts: dict[str, int] = {}

    transactions = await monarch.get_all_transactions(lookback_days)
    counts["transactions"] = bq.merge_upsert("transactions", transactions).source_rows

    accounts = await monarch.get_accounts()
    counts["accounts"] = bq.merge_upsert("accounts", accounts).source_rows

    categories = await monarch.get_categories()
    counts["categories"] = bq.merge_upsert("categories", categories).source_rows

    tags = await monarch.get_tags()
    counts["tags"] = bq.merge_upsert("tags", tags).source_rows

    budgets = await monarch.get_budgets()
    # Budgets have no stable per-row id; keep the latest snapshot without
    # soft-deleting the previous one.
    snapshot: dict[str, Any] = {"id": "current", "budgets": budgets}
    counts["budgets"] = bq.merge_upsert("budgets", [snapshot], soft_delete=False).source_rows

    log.info("ingestion_complete", project=settings.gcp_project_id, dataset=DATASET, **counts)
    return counts
