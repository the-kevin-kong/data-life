"""A session-persisting wrapper over the monarchmoney fork.

Authentication is fully automated for scheduled runs:

1. Load a saved session from Secret Manager and validate it (no login call).
2. If missing/expired, log in with email + password + the TOTP seed
   (``mfa_secret_key``) so no interactive MFA prompt is ever required.
3. Persist the refreshed session back to Secret Manager for next time.

Uses the monarchmoneycommunity fork (current api.monarch.com). Sessions last
months, so login runs rarely.

Read/write methods normalize the library's GraphQL response shapes into plain
lists/dicts. Response-shape assumptions are marked; if the fork's schema
differs, adjust the extraction helpers here in one place.
"""

from __future__ import annotations

import contextlib
import os
import tempfile
from datetime import date, timedelta
from typing import Any

from dl_common import SecretManager, get_logger, get_settings
from monarchmoney import MonarchMoney

log = get_logger(__name__)

_PAGE_SIZE = 1000


class MonarchClient:
    def __init__(self, secrets: SecretManager | None = None) -> None:
        self._settings = get_settings()
        self._secrets = secrets or SecretManager()
        self._mm = MonarchMoney()
        self._logged_in = False

    # -- auth ------------------------------------------------------------
    async def login(self) -> None:
        """Authenticate, reusing a persisted session when possible."""
        if self._logged_in:
            return

        if await self._try_saved_session():
            self._logged_in = True
            log.info("monarch_login", method="saved_session")
            return

        await self._mm.login(
            email=self._secrets.get(self._settings.monarch_email_secret),
            password=self._secrets.get(self._settings.monarch_password_secret),
            mfa_secret_key=self._secrets.get(self._settings.monarch_mfa_secret),
            use_saved_session=False,
            save_session=False,
        )
        self._persist_session()
        self._logged_in = True
        log.info("monarch_login", method="credentials")

    async def _try_saved_session(self) -> bool:
        blob = self._secrets.get_optional_bytes(self._settings.monarch_session_secret)
        if not blob:
            return False
        path = _write_temp_session(blob)
        try:
            self._mm.load_session(path)
            await self._mm.get_accounts()  # cheap validation call
            return True
        except Exception as exc:  # any failure => fall back to login
            log.warning("saved_session_invalid", error=str(exc))
            return False
        finally:
            _safe_unlink(path)

    def _persist_session(self) -> None:
        path = os.path.join(tempfile.gettempdir(), "mm_session")
        try:
            self._mm.save_session(path)
            with open(path, "rb") as fh:
                self._secrets.add_version(self._settings.monarch_session_secret, fh.read())
            log.info("monarch_session_persisted")
        finally:
            _safe_unlink(path)

    # -- reads -----------------------------------------------------------
    async def get_all_transactions(self, lookback_days: int | None = None) -> list[dict[str, Any]]:
        """Return the full set of transactions in the lookback window."""
        days = lookback_days or self._settings.ingest_transaction_lookback_days
        today = date.today()
        start = (today - timedelta(days=days)).isoformat()
        end = today.isoformat()
        results: list[dict[str, Any]] = []
        offset = 0
        while True:
            resp = await self._mm.get_transactions(
                limit=_PAGE_SIZE, offset=offset, start_date=start, end_date=end
            )
            page = _extract(resp, "allTransactions", "results")
            results.extend(page)
            if len(page) < _PAGE_SIZE:
                break
            offset += _PAGE_SIZE
        log.info("fetched_transactions", count=len(results))
        return results

    async def get_accounts(self) -> list[dict[str, Any]]:
        return list(_extract(await self._mm.get_accounts(), "accounts"))

    async def get_categories(self) -> list[dict[str, Any]]:
        return list(_extract(await self._mm.get_transaction_categories(), "categories"))

    async def get_tags(self) -> list[dict[str, Any]]:
        resp = await self._mm.get_transaction_tags()
        return list(_extract(resp, "householdTransactionTags") or _extract(resp, "tags"))

    async def get_budgets(self) -> dict[str, Any]:
        resp = await self._mm.get_budgets()
        return resp if isinstance(resp, dict) else {}

    # -- splitter support -----------------------------------------------
    async def get_transaction_splits(self, transaction_id: str) -> list[dict[str, Any]]:
        resp = await self._mm.get_transaction_splits(transaction_id)
        return list(_extract(resp, "getTransaction", "splitTransactions"))

    async def update_transaction_splits(
        self, transaction_id: str, split_data: list[dict[str, Any]]
    ) -> Any:
        return await self._mm.update_transaction_splits(transaction_id, split_data)

    async def set_transaction_tags(self, transaction_id: str, tag_ids: list[str]) -> Any:
        return await self._mm.set_transaction_tags(transaction_id, tag_ids)


def _write_temp_session(blob: bytes) -> str:
    fd, path = tempfile.mkstemp()
    with os.fdopen(fd, "wb") as fh:
        fh.write(blob)
    return path


def _safe_unlink(path: str) -> None:
    with contextlib.suppress(OSError):
        os.unlink(path)


def _extract(resp: Any, *keys: str) -> Any:
    """Walk nested dict keys defensively; return [] for a missing leaf list.

    Handles the common GraphQL envelope shapes without exploding when a key is
    absent, so a schema tweak in the fork degrades gracefully.
    """
    node: Any = resp
    for key in keys:
        if not isinstance(node, dict) or key not in node:
            return []
        node = node[key]
    if node is None:
        return []
    return node
