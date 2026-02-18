"""AWS Secrets Manager credential store implementation.

Provides secret listing with rotation metadata and credential rotation
via the AWS Secrets Manager SDK.
"""

import asyncio
from datetime import datetime
from functools import partial
from typing import Any

import structlog

from shieldops.agents.security.protocols import CredentialStore

logger = structlog.get_logger()


class AWSSecretsManagerStore(CredentialStore):
    """Credential store backed by AWS Secrets Manager.

    Supports listing secrets with rotation metadata and triggering
    immediate secret rotation via the RotateSecret API.

    Args:
        region: AWS region for Secrets Manager.
    """

    store_name = "aws_secrets_manager"

    def __init__(self, region: str = "us-east-1") -> None:
        self._region = region
        self._client: Any = None

    def _ensure_client(self) -> None:
        """Lazily initialize the boto3 Secrets Manager client."""
        if self._client is None:
            import boto3

            self._client = boto3.client("secretsmanager", region_name=self._region)

    async def _run_sync(self, func: Any, *args: Any, **kwargs: Any) -> Any:
        """Run a synchronous boto3 call in a thread executor."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, partial(func, *args, **kwargs))

    async def list_credentials(self, environment: str | None = None) -> list[dict[str, Any]]:
        """List secrets from AWS Secrets Manager with rotation metadata.

        Optionally filters secrets by environment tag. Returns a list of
        credential dicts with standardized keys.

        Args:
            environment: Optional environment filter (matches 'Environment' tag).
        """
        self._ensure_client()
        credentials: list[dict[str, Any]] = []

        try:
            paginator = self._client.get_paginator("list_secrets")
            filters: list[dict[str, Any]] = []
            if environment:
                filters.append({"Key": "tag-value", "Values": [environment]})

            page_kwargs: dict[str, Any] = {}
            if filters:
                page_kwargs["Filters"] = filters

            async for page in self._async_paginate(paginator, **page_kwargs):
                for secret in page.get("SecretList", []):
                    credential = self._parse_secret(secret)
                    credentials.append(credential)

        except Exception as e:
            logger.error("aws_secrets_list_failed", error=str(e))

        logger.info(
            "aws_secrets_list_complete",
            count=len(credentials),
            environment=environment,
        )
        return credentials

    async def _async_paginate(self, paginator: Any, **kwargs: Any) -> Any:
        """Yield pages from a boto3 paginator asynchronously."""
        pages = await self._run_sync(paginator.paginate, **kwargs)
        # boto3 paginators return iterables; we iterate in executor
        page_list: list[dict[str, Any]] = await self._run_sync(lambda: list(pages))
        for page in page_list:
            yield page

    def _parse_secret(self, secret: dict[str, Any]) -> dict[str, Any]:
        """Parse a Secrets Manager secret into a standardized credential dict."""
        tags = {tag["Key"]: tag["Value"] for tag in secret.get("Tags", [])}

        rotation_enabled = secret.get("RotationEnabled", False)
        last_rotated = secret.get("LastRotatedDate")
        last_accessed = secret.get("LastAccessedDate")

        # Determine credential type from tags or name
        credential_type = tags.get("CredentialType", "secret")
        service = tags.get("Service", secret.get("Name", "unknown"))

        # Calculate expiry from rotation rules
        expires_at = None
        if rotation_enabled and last_rotated:
            rotation_rules = secret.get("RotationRules", {})
            rotation_days = rotation_rules.get("AutomaticallyAfterDays", 90)
            if isinstance(last_rotated, datetime):
                from datetime import timedelta

                expires_at = last_rotated + timedelta(days=rotation_days)

        return {
            "credential_id": secret.get("ARN", secret.get("Name", "")),
            "credential_type": credential_type,
            "service": service,
            "expires_at": expires_at,
            "last_rotated": last_rotated,
            "last_accessed": last_accessed,
            "rotation_enabled": rotation_enabled,
            "name": secret.get("Name", ""),
            "tags": tags,
        }

    async def rotate_credential(self, credential_id: str, credential_type: str) -> dict[str, Any]:
        """Trigger immediate rotation of a secret in AWS Secrets Manager.

        Args:
            credential_id: The ARN or name of the secret.
            credential_type: The type of credential (for logging).

        Returns:
            Result dict with rotation status.
        """
        self._ensure_client()

        logger.info(
            "aws_secrets_rotate_start",
            credential_id=credential_id,
            credential_type=credential_type,
        )

        try:
            response = await self._run_sync(
                self._client.rotate_secret,
                SecretId=credential_id,
            )

            version_id = response.get("VersionId", "")

            logger.info(
                "aws_secrets_rotate_success",
                credential_id=credential_id,
                version_id=version_id,
            )

            return {
                "credential_id": credential_id,
                "credential_type": credential_type,
                "service": response.get("Name", ""),
                "success": True,
                "message": f"Rotation initiated, new version: {version_id}",
                "new_expiry": None,
                "version_id": version_id,
            }

        except Exception as e:
            logger.error(
                "aws_secrets_rotate_failed",
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
