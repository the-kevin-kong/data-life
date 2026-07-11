"""Splitter orchestration.

Finds recent transactions carrying a rule's trigger tag, computes their legs,
and (unless dry-run) writes the splits back to Monarch and marks them done.

Idempotency has two guards:
  1. Skip transactions already tagged with the "done" tag.
  2. Skip transactions Monarch already reports as split.
After a successful split the transaction is tagged done.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from dl_common import get_logger, get_settings
from dl_monarch import MonarchClient

from dl_splitter.engine import compute_legs
from dl_splitter.rules import SplitRules, load_rules

log = get_logger(__name__)

# 90 days is plenty of lookback to catch a newly tagged transaction.
_SPLIT_LOOKBACK_DAYS = 90


def _tag_names(txn: dict[str, Any]) -> list[str]:
    return [str(t["name"]) for t in txn.get("tags", []) if isinstance(t, dict) and t.get("name")]


def _tag_ids(txn: dict[str, Any]) -> list[str]:
    return [str(t["id"]) for t in txn.get("tags", []) if isinstance(t, dict) and t.get("id")]


def _already_split(txn: dict[str, Any]) -> bool:
    return bool(txn.get("isSplitTransaction") or txn.get("splitTransactions"))


async def run_splitter(
    dry_run: bool | None = None, rules: SplitRules | None = None
) -> dict[str, Any]:
    settings = get_settings()
    dry = settings.split_dry_run if dry_run is None else dry_run
    rules = rules or load_rules()

    monarch = MonarchClient()
    await monarch.login()

    tag_id_by_name = {t.get("name"): t.get("id") for t in await monarch.get_tags()}
    done_tag_id = tag_id_by_name.get(settings.split_done_tag)
    if done_tag_id is None:
        log.warning("done_tag_missing", tag=settings.split_done_tag)

    transactions = await monarch.get_all_transactions(lookback_days=_SPLIT_LOOKBACK_DAYS)

    processed: list[dict[str, Any]] = []
    for txn in transactions:
        names = _tag_names(txn)
        if settings.split_done_tag in names:
            continue
        rule = next((rules.for_tag(t) for t in names if rules.for_tag(t)), None)
        if rule is None:
            continue
        if _already_split(txn):
            log.info("skip_already_split", transaction_id=txn.get("id"), tag=rule.tag)
            continue

        legs = compute_legs(rule, float(txn["amount"]))
        entry: dict[str, Any] = {
            "transaction_id": txn.get("id"),
            "tag": rule.tag,
            "total": float(txn["amount"]),
            "legs": [asdict(leg) for leg in legs],
        }

        if dry:
            entry["action"] = "dry-run"
        else:
            split_data = [{"amount": leg.amount, "categoryId": leg.category_id} for leg in legs]
            await monarch.update_transaction_splits(txn["id"], split_data)
            if done_tag_id is not None:
                await monarch.set_transaction_tags(txn["id"], [*_tag_ids(txn), done_tag_id])
            entry["action"] = "split"

        processed.append(entry)
        log.info("split_planned" if dry else "split_applied", **entry)

    result = {"dry_run": dry, "count": len(processed), "transactions": processed}
    log.info("splitter_complete", dry_run=dry, count=len(processed))
    return result
