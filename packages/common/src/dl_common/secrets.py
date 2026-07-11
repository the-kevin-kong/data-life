"""Thin wrapper over Google Secret Manager.

Secrets are created (empty) by Terraform; values are added out-of-band. This
client reads the latest version and can append new versions (used to persist
the refreshed Monarch session blob).
"""

from __future__ import annotations

import google.auth
from google.api_core.exceptions import NotFound
from google.cloud import secretmanager

from dl_common.config import get_settings


class SecretManager:
    def __init__(self, project_id: str | None = None) -> None:
        project = project_id or get_settings().gcp_project_id
        if not project:
            # Resolve from Application Default Credentials when unset.
            _, detected = google.auth.default()
            project = detected or ""
        self._project = project
        self._client = secretmanager.SecretManagerServiceClient()

    def _version_path(self, secret_id: str, version: str = "latest") -> str:
        return f"projects/{self._project}/secrets/{secret_id}/versions/{version}"

    def get_bytes(self, secret_id: str, version: str = "latest") -> bytes:
        """Return the raw payload of a secret version. Raises if absent."""
        response = self._client.access_secret_version(name=self._version_path(secret_id, version))
        return response.payload.data

    def get(self, secret_id: str, version: str = "latest") -> str:
        """Return a secret value as a UTF-8 string. Raises if absent."""
        return self.get_bytes(secret_id, version).decode("utf-8")

    def get_optional_bytes(self, secret_id: str, version: str = "latest") -> bytes | None:
        """Return the payload, or None if the secret has no accessible version."""
        try:
            return self.get_bytes(secret_id, version)
        except NotFound:
            return None

    def add_version(self, secret_id: str, payload: bytes) -> None:
        """Append a new version to an existing secret container."""
        parent = f"projects/{self._project}/secrets/{secret_id}"
        self._client.add_secret_version(
            parent=parent, payload=secretmanager.SecretPayload(data=payload)
        )
