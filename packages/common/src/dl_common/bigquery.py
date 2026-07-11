"""BigQuery access + the raw-layer MERGE-upsert loader.

The raw layer keeps exactly one row per source record (low storage) while
still capturing deletions: records that vanish from a full pull are
soft-deleted rather than dropped. Every raw table shares one schema:

    id            STRING     -- natural key from Monarch
    data          JSON       -- full source record
    _ingested_at  TIMESTAMP  -- first seen
    _updated_at   TIMESTAMP  -- last change
    _is_deleted   BOOL       -- true once it disappears from source
    _deleted_at   TIMESTAMP  -- when that happened

dbt reads `data` with JSON accessors and filters `where not _is_deleted`.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from google.api_core.exceptions import NotFound
from google.cloud import bigquery

from dl_common.config import get_settings
from dl_common.logging import get_logger

log = get_logger(__name__)

RAW_SCHEMA: list[bigquery.SchemaField] = [
    bigquery.SchemaField("id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("data", "JSON", mode="NULLABLE"),
    bigquery.SchemaField("_ingested_at", "TIMESTAMP"),
    bigquery.SchemaField("_updated_at", "TIMESTAMP"),
    bigquery.SchemaField("_is_deleted", "BOOL"),
    bigquery.SchemaField("_deleted_at", "TIMESTAMP"),
]

_STAGING_SCHEMA: list[bigquery.SchemaField] = [
    bigquery.SchemaField("id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("data", "STRING"),
]


@dataclass
class UpsertResult:
    """Outcome of a merge_upsert call."""

    table: str
    source_rows: int
    skipped: bool = False


class BigQueryClient:
    def __init__(self, project_id: str | None = None, dataset: str | None = None) -> None:
        settings = get_settings()
        # Default dataset for this client; the pipeline sets it (e.g. "monarch").
        self._dataset = dataset
        self._client = bigquery.Client(project=(project_id or settings.gcp_project_id) or None)
        self._project = self._client.project

    # -- helpers ---------------------------------------------------------
    def _fqtn(self, table: str, dataset: str | None = None) -> str:
        ds = dataset or self._dataset
        if not ds:
            raise ValueError("no dataset set; pass dataset= to BigQueryClient or the call")
        return f"{self._project}.{ds}.{table}"

    def ensure_dataset(self, dataset: str, location: str = "US") -> None:
        ref = bigquery.Dataset(f"{self._project}.{dataset}")
        ref.location = location
        self._client.create_dataset(ref, exists_ok=True)

    def ensure_raw_table(self, table: str) -> None:
        fqtn = self._fqtn(table)
        try:
            self._client.get_table(fqtn)
        except NotFound:
            tbl = bigquery.Table(fqtn, schema=RAW_SCHEMA)
            tbl.clustering_fields = ["id"]
            self._client.create_table(tbl)
            log.info("created_raw_table", table=fqtn)

    def query(self, sql: str, params: list[bigquery.ScalarQueryParameter] | None = None) -> Any:
        job_config = bigquery.QueryJobConfig(query_parameters=params or [])
        return self._client.query(sql, job_config=job_config).result()

    # -- the core loader -------------------------------------------------
    def merge_upsert(
        self,
        table: str,
        records: Iterable[Mapping[str, Any]],
        *,
        key: str = "id",
        soft_delete: bool = True,
    ) -> UpsertResult:
        """Upsert ``records`` into ``raw.<table>`` keyed on ``key``.

        With ``soft_delete=True`` (the default), rows present in the target but
        absent from ``records`` are flagged deleted. Because that would delete
        everything on an empty input, an empty pull is treated as a no-op.
        """
        rows = [dict(r) for r in records]
        self.ensure_raw_table(table)

        if not rows:
            log.warning("merge_upsert_empty_input_skipped", table=table)
            return UpsertResult(table=table, source_rows=0, skipped=True)

        target = self._fqtn(table)
        staging = self._fqtn(f"_stg_{table}_{uuid.uuid4().hex[:8]}")

        payload = [{"id": str(r[key]), "data": json.dumps(r, default=str)} for r in rows]
        load_job = self._client.load_table_from_json(
            payload,
            staging,
            job_config=bigquery.LoadJobConfig(
                schema=_STAGING_SCHEMA,
                write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
                source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
            ),
        )
        load_job.result()

        try:
            self._client.query(self._merge_sql(target, staging, soft_delete)).result()
        finally:
            self._client.delete_table(staging, not_found_ok=True)

        log.info("merge_upsert_done", table=table, source_rows=len(rows))
        return UpsertResult(table=table, source_rows=len(rows))

    @staticmethod
    def _merge_sql(target: str, staging: str, soft_delete: bool) -> str:
        soft_delete_clause = (
            """
            WHEN NOT MATCHED BY SOURCE AND T._is_deleted = FALSE THEN
              UPDATE SET T._is_deleted = TRUE, T._deleted_at = CURRENT_TIMESTAMP()
            """
            if soft_delete
            else ""
        )
        return f"""
            MERGE `{target}` T
            USING `{staging}` S
            ON T.id = S.id
            WHEN MATCHED THEN UPDATE SET
              T.data = PARSE_JSON(S.data),
              T._updated_at = CURRENT_TIMESTAMP(),
              T._is_deleted = FALSE,
              T._deleted_at = NULL
            WHEN NOT MATCHED BY TARGET THEN
              INSERT (id, data, _ingested_at, _updated_at, _is_deleted, _deleted_at)
              VALUES (S.id, PARSE_JSON(S.data), CURRENT_TIMESTAMP(),
                      CURRENT_TIMESTAMP(), FALSE, NULL)
            {soft_delete_clause}
        """
