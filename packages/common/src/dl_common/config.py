"""Centralized settings, loaded from environment / .env.

Every service reads config through :func:`get_settings` so behavior is
consistent between local runs and Cloud Run (where values come from the
service environment, populated from Secret Manager / Terraform).
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- GCP ---
    # Left empty on purpose so the project id never lives in the repo. Set
    # GCP_PROJECT_ID in the environment (local .env / Cloud Run / NAS). When
    # empty, clients fall back to the ADC-detected project.
    gcp_project_id: str = ""
    gcp_region: str = "us-central1"

    # --- BigQuery datasets ---
    # The raw/source dataset name is dictated by each ingestion pipeline, not
    # configured here. Downstream datasets:
    bq_staging_dataset: str = "staging"
    bq_marts_dataset: str = "marts"

    # --- Secret Manager secret ids (values live in GCP) ---
    monarch_email_secret: str = "monarch-email"
    monarch_password_secret: str = "monarch-password"
    monarch_mfa_secret: str = "monarch-mfa-secret"
    monarch_session_secret: str = "monarch-session"

    # --- Ingestion ---
    ingest_transaction_lookback_days: int = 3650

    # --- Splitter ---
    split_trigger_tag_prefix: str = "split:"
    split_done_tag: str = "split:done"
    split_dry_run: bool = True

    # --- Logging ---
    log_level: str = "INFO"
    log_json: bool = False


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
