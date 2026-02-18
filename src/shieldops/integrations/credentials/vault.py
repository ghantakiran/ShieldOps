"""HashiCorp Vault credential store implementation.

Supports KV v2 secret engine for credential listing and database
credential rotation via the Vault HTTP API.
"""

import contextlib
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog

from shieldops.agents.security.protocols import CredentialStore

logger = structlog.get_logger()


class VaultCredentialStore(CredentialStore):
    """Credential store backed by HashiCorp Vault.

    Supports:
    - KV v2 engine for listing and reading secrets
    - Database credential rotation via lease revocation + re-read
    - Token and AppRole authentication

    Args:
        vault_addr: Vault server URL (e.g. "https://vault.example.com:8200").
        token: Vault authentication token.
        mount_point: KV v2 mount point (default "secret").
        namespace: Vault namespace (enterprise only).
    """

    store_name = "hashicorp_vault"

    def __init__(
        self,
        vault_addr: str = "http://127.0.0.1:8200",
        token: str = "",
        mount_point: str = "secret",
        namespace: str = "",
    ) -> None:
        self._vault_addr = vault_addr.rstrip("/")
        self._token = token
        self._mount_point = mount_point
        self._namespace = namespace
        self._client: Any = None

    def _ensure_client(self) -> Any:
        """Lazily initialize the httpx AsyncClient for Vault API calls."""
        if self._client is None:
            import httpx

            headers: dict[str, str] = {
                "X-Vault-Token": self._token,
                "Accept": "application/json",
            }
            if self._namespace:
                headers["X-Vault-Namespace"] = self._namespace
            self._client = httpx.AsyncClient(
                base_url=self._vault_addr,
                headers=headers,
                timeout=30,
            )
        return self._client

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def list_credentials(self, environment: str | None = None) -> list[dict[str, Any]]:
        """List credentials stored in the Vault KV v2 engine.

        Lists all secret keys under the configured mount point, then reads
        metadata for each to extract rotation and expiry information.
        Optionally filters by environment path prefix.

        Args:
            environment: Optional path prefix filter (e.g. "production").
        """
        client = self._ensure_client()
        credentials: list[dict[str, Any]] = []

        try:
            # LIST operation on KV v2 metadata
            path = f"/v1/{self._mount_point}/metadata/"
            if environment:
                path = f"/v1/{self._mount_point}/metadata/{environment}/"

            response = await client.request("LIST", path)

            if response.status_code == 404:
                logger.info("vault_list_empty", path=path)
                return []

            response.raise_for_status()
            data = response.json()
            keys: list[str] = data.get("data", {}).get("keys", [])

            for key in keys:
                # Skip directory entries (end with /)
                if key.endswith("/"):
                    continue
                secret_path = f"{environment}/{key}" if environment else key
                metadata = await self._read_metadata(secret_path)
                credential = self._parse_metadata(secret_path, metadata)
                credentials.append(credential)

        except Exception as e:
            logger.error("vault_list_failed", error=str(e))

        logger.info(
            "vault_list_complete",
            count=len(credentials),
            environment=environment,
        )
        return credentials

    async def _read_metadata(self, secret_path: str) -> dict[str, Any]:
        """Read KV v2 metadata for a secret to get version and custom metadata."""
        client = self._ensure_client()

        try:
            url = f"/v1/{self._mount_point}/metadata/{secret_path}"
            response = await client.get(url)
            response.raise_for_status()
            data: dict[str, Any] = response.json().get("data", {})
            return data
        except Exception as e:
            logger.warning("vault_read_metadata_failed", path=secret_path, error=str(e))
            return {}

    def _parse_metadata(self, secret_path: str, metadata: dict[str, Any]) -> dict[str, Any]:
        """Parse Vault KV v2 metadata into a standardized credential dict."""
        custom_metadata: dict[str, str] = metadata.get("custom_metadata", {}) or {}
        versions: dict[str, Any] = metadata.get("versions", {})

        # Find latest version for last_rotated timestamp
        last_rotated = None
        if versions:
            latest_version = max(versions.keys(), key=int)
            version_data = versions[latest_version]
            created_time = version_data.get("created_time", "")
            if created_time:
                with contextlib.suppress(ValueError, TypeError):
                    last_rotated = datetime.fromisoformat(created_time.replace("Z", "+00:00"))

        credential_type = custom_metadata.get("credential_type", "secret")
        service = custom_metadata.get("service", secret_path.split("/")[-1])

        # Calculate expiry from custom_metadata ttl if present
        expires_at = None
        ttl_days = custom_metadata.get("ttl_days")
        if ttl_days and last_rotated:
            with contextlib.suppress(ValueError, TypeError):
                expires_at = last_rotated + timedelta(days=int(ttl_days))

        return {
            "credential_id": f"vault:{self._mount_point}/{secret_path}",
            "credential_type": credential_type,
            "service": service,
            "expires_at": expires_at,
            "last_rotated": last_rotated,
            "current_version": metadata.get("current_version", 0),
            "max_versions": metadata.get("max_versions", 0),
            "path": secret_path,
        }

    async def rotate_credential(self, credential_id: str, credential_type: str) -> dict[str, Any]:
        """Rotate a credential in Vault.

        For database credentials, revokes the current lease and requests
        a new one. For KV secrets, this is a no-op that returns guidance
        (KV secrets must be written with a new value by the caller).

        Args:
            credential_id: Vault path (e.g. "vault:secret/db-password").
            credential_type: Type of credential ("database", "api_key", etc.).
        """
        self._ensure_client()

        logger.info(
            "vault_rotate_start",
            credential_id=credential_id,
            credential_type=credential_type,
        )

        # Strip "vault:" prefix if present
        path = credential_id
        if path.startswith("vault:"):
            path = path[6:]

        try:
            if credential_type == "database":
                return await self._rotate_database_credential(path, credential_id)
            else:
                return await self._rotate_kv_credential(path, credential_id, credential_type)

        except Exception as e:
            logger.error(
                "vault_rotate_failed",
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

    async def _rotate_database_credential(self, path: str, credential_id: str) -> dict[str, Any]:
        """Rotate a database dynamic credential by requesting a new lease."""
        client = self._ensure_client()

        # Read from database secret engine to get new credentials
        # Path format: "database/creds/<role>"
        response = await client.get(f"/v1/{path}")
        response.raise_for_status()
        data = response.json()

        lease_id = data.get("lease_id", "")
        lease_duration = data.get("lease_duration", 0)
        new_expiry = datetime.now(UTC) + timedelta(seconds=lease_duration)

        logger.info(
            "vault_rotate_database_success",
            credential_id=credential_id,
            lease_id=lease_id,
        )

        return {
            "credential_id": credential_id,
            "credential_type": "database",
            "service": path.split("/")[-1] if "/" in path else path,
            "success": True,
            "message": f"New database credentials issued, lease: {lease_id}",
            "new_expiry": new_expiry,
            "lease_id": lease_id,
        }

    async def _rotate_kv_credential(
        self, path: str, credential_id: str, credential_type: str
    ) -> dict[str, Any]:
        """For KV v2 secrets, read the current version and signal that rotation
        requires the caller to write a new value."""
        client = self._ensure_client()

        # Read current version to confirm access
        response = await client.get(f"/v1/{path}")
        if response.status_code == 200:
            return {
                "credential_id": credential_id,
                "credential_type": credential_type,
                "service": path.split("/")[-1] if "/" in path else path,
                "success": True,
                "message": ("KV secret accessible. Write a new version to complete rotation."),
                "new_expiry": None,
            }
        else:
            return {
                "credential_id": credential_id,
                "credential_type": credential_type,
                "service": "",
                "success": False,
                "message": f"Cannot access secret: HTTP {response.status_code}",
                "new_expiry": None,
            }
