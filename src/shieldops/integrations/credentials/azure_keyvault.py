"""Azure Key Vault credential store implementation.

Provides secret listing and credential rotation via the Azure Key Vault
SDK (azure-keyvault-secrets).
"""

import asyncio
from functools import partial
from typing import Any

import structlog

from shieldops.agents.security.protocols import CredentialStore

logger = structlog.get_logger()


class AzureKeyVaultStore(CredentialStore):
    """Credential store backed by Azure Key Vault.

    Lists secrets via ``list_properties_of_secrets()`` and rotates
    credentials via ``set_secret()``.

    Args:
        vault_url: Azure Key Vault URL (e.g. "https://myvault.vault.azure.net").
    """

    store_name = "azure_keyvault"

    def __init__(self, vault_url: str) -> None:
        self._vault_url = vault_url
        self._client: Any = None

    def _ensure_client(self) -> Any:
        """Lazily initialize the SecretClient with DefaultAzureCredential."""
        if self._client is None:
            from azure.identity import DefaultAzureCredential
            from azure.keyvault.secrets import SecretClient

            credential = DefaultAzureCredential()
            self._client = SecretClient(vault_url=self._vault_url, credential=credential)
        return self._client

    async def _run_sync(self, func: Any, *args: Any, **kwargs: Any) -> Any:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, partial(func, *args, **kwargs))

    async def list_credentials(self, environment: str | None = None) -> list[dict[str, Any]]:
        """List secrets from Azure Key Vault.

        Optionally filters by the ``environment`` tag.
        """
        client = self._ensure_client()
        credentials: list[dict[str, Any]] = []

        try:
            properties_iter = await self._run_sync(client.list_properties_of_secrets)
            properties_list: list[Any] = await self._run_sync(list, properties_iter)

            for props in properties_list:
                credential = self._parse_properties(props)
                if environment:
                    tags = credential.get("tags", {})
                    if tags.get("environment") != environment:
                        continue
                credentials.append(credential)

        except Exception as e:
            logger.error("azure_keyvault_list_failed", error=str(e))

        logger.info(
            "azure_keyvault_list_complete",
            count=len(credentials),
            environment=environment,
        )
        return credentials

    def _parse_properties(self, props: Any) -> dict[str, Any]:
        """Parse Azure Key Vault secret properties into a standardized dict."""
        tags: dict[str, str] = dict(props.tags) if props.tags else {}

        credential_type = tags.get("credential_type", "secret")
        service = tags.get("service", props.name or "unknown")

        expires_at = None
        if props.expires_on:
            expires_at = props.expires_on

        last_rotated = None
        if props.updated_on:
            last_rotated = props.updated_on
        elif props.created_on:
            last_rotated = props.created_on

        return {
            "credential_id": f"azure:{props.name}",
            "credential_type": credential_type,
            "service": service,
            "expires_at": expires_at,
            "last_rotated": last_rotated,
            "created_at": props.created_on,
            "enabled": props.enabled,
            "content_type": props.content_type,
            "tags": tags,
            "name": props.name,
        }

    async def rotate_credential(self, credential_id: str, credential_type: str) -> dict[str, Any]:
        """Rotate a credential by writing a new version in Azure Key Vault.

        Sets a new secret value which auto-creates a new version.
        """
        client = self._ensure_client()

        logger.info(
            "azure_keyvault_rotate_start",
            credential_id=credential_id,
            credential_type=credential_type,
        )

        # Strip "azure:" prefix
        secret_name = credential_id
        if secret_name.startswith("azure:"):
            secret_name = secret_name[6:]

        try:
            result = await self._run_sync(
                client.set_secret,
                secret_name,
                "ROTATED_PLACEHOLDER",
            )

            version = getattr(result.properties, "version", "")

            logger.info(
                "azure_keyvault_rotate_success",
                credential_id=credential_id,
                version=version,
            )

            return {
                "credential_id": credential_id,
                "credential_type": credential_type,
                "service": secret_name,
                "success": True,
                "message": f"New version created: {version}",
                "new_expiry": None,
                "version": version,
            }

        except Exception as e:
            logger.error(
                "azure_keyvault_rotate_failed",
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
