"""Tests for the HashiCorp Vault credential store implementation.

Tests cover:
- list_credentials (with/without environment, empty, API error)
- Metadata parsing (versions, custom_metadata, TTL-based expiry)
- rotate_credential (database, KV, errors)
- Initialization and Vault auth headers
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from shieldops.integrations.credentials.vault import VaultCredentialStore

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_list_response(keys: list[str]) -> MagicMock:
    """Build a mock Vault LIST response."""
    resp = MagicMock()
    resp.status_code = 200
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {"data": {"keys": keys}}
    return resp


def _make_metadata_response(
    current_version: int = 2,
    created_time: str = "2024-06-01T00:00:00Z",
    custom_metadata: dict[str, str] | None = None,
) -> MagicMock:
    """Build a mock Vault metadata response."""
    resp = MagicMock()
    resp.status_code = 200
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {
        "data": {
            "current_version": current_version,
            "max_versions": 10,
            "versions": {
                str(current_version): {
                    "created_time": created_time,
                    "destroyed": False,
                },
            },
            "custom_metadata": custom_metadata
            or {
                "credential_type": "database",
                "service": "postgres",
                "ttl_days": "30",
            },
        }
    }
    return resp


def _make_404_response() -> MagicMock:
    resp = MagicMock()
    resp.status_code = 404
    return resp


@pytest.fixture
def store() -> VaultCredentialStore:
    """Create a VaultCredentialStore with mocked HTTP client."""
    s = VaultCredentialStore(
        vault_addr="https://vault.example.com:8200",
        token="test-token",
        mount_point="secret",
    )
    s._client = AsyncMock()
    return s


# ============================================================================
# list_credentials
# ============================================================================


class TestListCredentials:
    @pytest.mark.asyncio
    async def test_list_returns_credentials(self, store: VaultCredentialStore) -> None:
        list_resp = _make_list_response(["db-password", "api-key"])
        metadata_resp = _make_metadata_response()

        store._client.request = AsyncMock(return_value=list_resp)
        store._client.get = AsyncMock(return_value=metadata_resp)

        credentials = await store.list_credentials()

        assert len(credentials) == 2
        assert credentials[0]["path"] == "db-password"
        assert credentials[1]["path"] == "api-key"

    @pytest.mark.asyncio
    async def test_list_with_environment(self, store: VaultCredentialStore) -> None:
        list_resp = _make_list_response(["db-password"])
        metadata_resp = _make_metadata_response()

        store._client.request = AsyncMock(return_value=list_resp)
        store._client.get = AsyncMock(return_value=metadata_resp)

        credentials = await store.list_credentials(environment="production")

        assert len(credentials) == 1
        assert credentials[0]["path"] == "production/db-password"
        # Verify LIST was called with correct path
        store._client.request.assert_called_once()
        call_args = store._client.request.call_args
        assert "production" in call_args[0][1]

    @pytest.mark.asyncio
    async def test_list_empty_404(self, store: VaultCredentialStore) -> None:
        store._client.request = AsyncMock(return_value=_make_404_response())

        credentials = await store.list_credentials()

        assert credentials == []

    @pytest.mark.asyncio
    async def test_list_skips_directory_entries(self, store: VaultCredentialStore) -> None:
        list_resp = _make_list_response(["db-password", "subdirectory/", "api-key"])
        metadata_resp = _make_metadata_response()

        store._client.request = AsyncMock(return_value=list_resp)
        store._client.get = AsyncMock(return_value=metadata_resp)

        credentials = await store.list_credentials()

        # Should skip "subdirectory/"
        assert len(credentials) == 2
        paths = [c["path"] for c in credentials]
        assert "subdirectory/" not in paths

    @pytest.mark.asyncio
    async def test_list_api_error_returns_empty(self, store: VaultCredentialStore) -> None:
        store._client.request = AsyncMock(side_effect=Exception("Connection refused"))

        credentials = await store.list_credentials()

        assert credentials == []


# ============================================================================
# Metadata parsing
# ============================================================================


class TestParseMetadata:
    def test_parse_with_custom_metadata(self, store: VaultCredentialStore) -> None:
        metadata = {
            "current_version": 3,
            "max_versions": 10,
            "versions": {
                "3": {"created_time": "2024-06-15T12:00:00Z"},
            },
            "custom_metadata": {
                "credential_type": "api_key",
                "service": "stripe",
                "ttl_days": "90",
            },
        }
        result = store._parse_metadata("payments/stripe-key", metadata)

        assert result["credential_type"] == "api_key"
        assert result["service"] == "stripe"
        assert result["current_version"] == 3
        assert result["last_rotated"] is not None

    def test_parse_with_ttl_calculates_expiry(self, store: VaultCredentialStore) -> None:
        metadata = {
            "current_version": 1,
            "versions": {
                "1": {"created_time": "2024-01-01T00:00:00Z"},
            },
            "custom_metadata": {"ttl_days": "30"},
        }
        result = store._parse_metadata("test-secret", metadata)

        assert result["expires_at"] is not None
        expected = datetime(2024, 1, 31, tzinfo=UTC)
        assert result["expires_at"] == expected

    def test_parse_without_custom_metadata(self, store: VaultCredentialStore) -> None:
        metadata = {
            "current_version": 1,
            "versions": {"1": {"created_time": "2024-06-01T00:00:00Z"}},
            "custom_metadata": None,
        }
        result = store._parse_metadata("db/password", metadata)

        assert result["credential_type"] == "secret"
        assert result["service"] == "password"  # Last path component

    def test_parse_empty_versions(self, store: VaultCredentialStore) -> None:
        metadata = {"current_version": 0, "versions": {}, "custom_metadata": {}}
        result = store._parse_metadata("test", metadata)

        assert result["last_rotated"] is None
        assert result["expires_at"] is None

    def test_credential_id_format(self, store: VaultCredentialStore) -> None:
        metadata = {"current_version": 1, "versions": {}, "custom_metadata": {}}
        result = store._parse_metadata("production/db-pass", metadata)

        assert result["credential_id"] == "vault:secret/production/db-pass"


# ============================================================================
# rotate_credential
# ============================================================================


class TestRotateCredential:
    @pytest.mark.asyncio
    async def test_rotate_database_credential(self, store: VaultCredentialStore) -> None:
        resp = MagicMock()
        resp.status_code = 200
        resp.raise_for_status = MagicMock()
        resp.json.return_value = {
            "lease_id": "database/creds/myapp/abc123",
            "lease_duration": 3600,
            "data": {"username": "v-myapp-abc", "password": "generated"},
        }
        store._client.get = AsyncMock(return_value=resp)

        result = await store.rotate_credential("vault:database/creds/myapp", "database")

        assert result["success"] is True
        assert result["credential_type"] == "database"
        assert result["new_expiry"] is not None
        assert "lease" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_rotate_kv_credential(self, store: VaultCredentialStore) -> None:
        resp = MagicMock()
        resp.status_code = 200
        store._client.get = AsyncMock(return_value=resp)

        result = await store.rotate_credential("vault:secret/data/api-key", "api_key")

        assert result["success"] is True
        assert "Write a new version" in result["message"]

    @pytest.mark.asyncio
    async def test_rotate_kv_not_found(self, store: VaultCredentialStore) -> None:
        resp = MagicMock()
        resp.status_code = 403
        store._client.get = AsyncMock(return_value=resp)

        result = await store.rotate_credential("vault:secret/data/missing", "api_key")

        assert result["success"] is False
        assert "403" in result["message"]

    @pytest.mark.asyncio
    async def test_rotate_api_error(self, store: VaultCredentialStore) -> None:
        store._client.get = AsyncMock(side_effect=Exception("Connection refused"))

        result = await store.rotate_credential("vault:secret/db-pw", "database")

        assert result["success"] is False
        assert "Connection refused" in result["message"]

    @pytest.mark.asyncio
    async def test_rotate_strips_vault_prefix(self, store: VaultCredentialStore) -> None:
        resp = MagicMock()
        resp.status_code = 200
        resp.raise_for_status = MagicMock()
        resp.json.return_value = {
            "lease_id": "db/creds/app/xyz",
            "lease_duration": 1800,
        }
        store._client.get = AsyncMock(return_value=resp)

        await store.rotate_credential("vault:database/creds/app", "database")

        # Should call with path stripped of "vault:" prefix
        store._client.get.assert_called_once()
        call_args = store._client.get.call_args
        assert "vault:" not in call_args[0][0]


# ============================================================================
# Initialization
# ============================================================================


class TestInit:
    def test_store_name(self) -> None:
        store = VaultCredentialStore()
        assert store.store_name == "hashicorp_vault"

    def test_default_addr(self) -> None:
        store = VaultCredentialStore()
        assert "127.0.0.1" in store._vault_addr

    def test_custom_config(self) -> None:
        store = VaultCredentialStore(
            vault_addr="https://vault.prod.internal:8200",
            token="s.mytoken",
            mount_point="kv",
            namespace="team-a",
        )
        assert store._vault_addr == "https://vault.prod.internal:8200"
        assert store._token == "s.mytoken"  # noqa: S105
        assert store._mount_point == "kv"
        assert store._namespace == "team-a"

    def test_client_initially_none(self) -> None:
        store = VaultCredentialStore()
        assert store._client is None

    def test_implements_credential_store(self) -> None:
        from shieldops.agents.security.protocols import CredentialStore

        assert issubclass(VaultCredentialStore, CredentialStore)

    def test_addr_trailing_slash_stripped(self) -> None:
        store = VaultCredentialStore(vault_addr="https://vault.example.com/")
        assert not store._vault_addr.endswith("/")
