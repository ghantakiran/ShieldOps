"""GCP Secret Manager credential store implementation.

Provides secret listing with labels-based filtering and credential
rotation via creating new secret versions.
"""

import asyncio
from functools import partial
from typing import Any

import structlog

from shieldops.agents.security.protocols import CredentialStore

logger = structlog.get_logger()


class GCPSecretManagerStore(CredentialStore):
    """Credential store backed by GCP Secret Manager.

    Lists secrets filtered by labels and rotates credentials by adding
    a new secret version.

    Args:
        project_id: GCP project ID.
    """

    store_name = "gcp_secret_manager"

    def __init__(self, project_id: str) -> None:
        self._project_id = project_id
        self._client: Any = None

    def _ensure_client(self) -> Any:
        """Lazily initialize the Secret Manager client."""
        if self._client is None:
            from google.cloud import secretmanager_v1

            self._client = secretmanager_v1.SecretManagerServiceClient()
        return self._client

    async def _run_sync(self, func: Any, *args: Any, **kwargs: Any) -> Any:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, partial(func, *args, **kwargs))

    @property
    def _parent(self) -> str:
        return f"projects/{self._project_id}"

    async def list_credentials(self, environment: str | None = None) -> list[dict[str, Any]]:
        """List secrets from GCP Secret Manager.

        Optionally filters by the ``environment`` label.
        """
        client = self._ensure_client()
        credentials: list[dict[str, Any]] = []

        try:
            request: dict[str, Any] = {"parent": self._parent}
            if environment:
                request["filter"] = f'labels.environment="{environment}"'

            secrets = await self._run_sync(client.list_secrets, request=request)

            for secret in secrets:
                credential = await self._parse_secret(secret)
                credentials.append(credential)

        except Exception as e:
            logger.error("gcp_secrets_list_failed", error=str(e))

        logger.info(
            "gcp_secrets_list_complete",
            count=len(credentials),
            environment=environment,
        )
        return credentials

    async def _parse_secret(self, secret: Any) -> dict[str, Any]:
        """Parse a GCP secret into a standardized credential dict."""
        labels: dict[str, str] = dict(secret.labels) if secret.labels else {}
        name = secret.name.split("/")[-1] if "/" in secret.name else secret.name

        credential_type = labels.get("credential_type", "secret")
        service = labels.get("service", name)

        # Get latest version metadata for last_rotated
        last_rotated = None
        expires_at = None
        try:
            client = self._ensure_client()
            version_name = f"{secret.name}/versions/latest"
            version = await self._run_sync(
                client.access_secret_version,
                request={"name": version_name},
            )
            if hasattr(version, "create_time") and version.create_time:
                last_rotated = version.create_time
        except Exception as exc:
            logger.debug("gcp_secret_version_not_found", secret=secret.name, error=str(exc))

        # Calculate expiry from labels if present
        ttl_days = labels.get("ttl_days")
        if ttl_days and last_rotated:
            try:
                from datetime import timedelta

                expires_at = last_rotated + timedelta(days=int(ttl_days))
            except (ValueError, TypeError):
                pass

        create_time = None
        if hasattr(secret, "create_time") and secret.create_time:
            create_time = secret.create_time

        return {
            "credential_id": f"gcp:{secret.name}",
            "credential_type": credential_type,
            "service": service,
            "expires_at": expires_at,
            "last_rotated": last_rotated,
            "created_at": create_time,
            "labels": labels,
            "name": name,
        }

    async def rotate_credential(self, credential_id: str, credential_type: str) -> dict[str, Any]:
        """Rotate a credential by adding a new secret version.

        For GCP Secret Manager, rotation means adding a new version.
        The caller must provide the new secret value via the credential store
        or an external rotation function.
        """
        client = self._ensure_client()

        logger.info(
            "gcp_secrets_rotate_start",
            credential_id=credential_id,
            credential_type=credential_type,
        )

        # Strip "gcp:" prefix if present
        secret_name = credential_id
        if secret_name.startswith("gcp:"):
            secret_name = secret_name[4:]

        try:
            # Add a placeholder version to signal rotation
            payload = b"ROTATED_PLACEHOLDER"
            response = await self._run_sync(
                client.add_secret_version,
                request={
                    "parent": secret_name,
                    "payload": {"data": payload},
                },
            )

            version_name = response.name if hasattr(response, "name") else ""

            logger.info(
                "gcp_secrets_rotate_success",
                credential_id=credential_id,
                version=version_name,
            )

            return {
                "credential_id": credential_id,
                "credential_type": credential_type,
                "service": secret_name.split("/")[-1] if "/" in secret_name else secret_name,
                "success": True,
                "message": f"New version created: {version_name}",
                "new_expiry": None,
                "version": version_name,
            }

        except Exception as e:
            logger.error(
                "gcp_secrets_rotate_failed",
                credential_id=credential_id,
                error=str(e),
            )
            return {
                "credential_id": credential_id,
                "credential_type": credential_type,
                "service": "",
                "success": False,
                "message": f"Rotation failed: {e}",
                "new_expiry": None,
            }
