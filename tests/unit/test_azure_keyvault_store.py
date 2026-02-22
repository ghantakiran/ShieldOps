"""Tests for Azure Key Vault credential store (F3)."""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from shieldops.integrations.credentials.azure_keyvault import AzureKeyVaultStore


class TestAzureKeyVaultStore:
    @pytest.fixture
    def store(self):
        return AzureKeyVaultStore(vault_url="https://myvault.vault.azure.net")

    def test_store_name(self, store):
        assert store.store_name == "azure_keyvault"

    @pytest.mark.asyncio
    async def test_list_credentials_empty(self, store):
        async def mock_run_sync(func, *args, **kwargs):
            return []

        store._client = MagicMock()
        store._run_sync = mock_run_sync
        result = await store.list_credentials()
        assert result == []

    @pytest.mark.asyncio
    async def test_list_credentials_with_secrets(self, store):
        mock_props = MagicMock()
        mock_props.name = "db-password"
        mock_props.tags = {"credential_type": "database", "service": "postgres"}
        mock_props.expires_on = datetime.now(UTC) + timedelta(days=30)
        mock_props.updated_on = datetime.now(UTC) - timedelta(days=5)
        mock_props.created_on = datetime.now(UTC) - timedelta(days=60)
        mock_props.enabled = True
        mock_props.content_type = "text/plain"

        call_count = [0]

        async def mock_run_sync(func, *args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return iter([mock_props])
            return [mock_props]

        store._client = MagicMock()
        store._run_sync = mock_run_sync
        result = await store.list_credentials()
        assert len(result) == 1
        assert result[0]["credential_type"] == "database"
        assert result[0]["service"] == "postgres"
        assert result[0]["expires_at"] is not None

    @pytest.mark.asyncio
    async def test_list_credentials_filter_environment(self, store):
        mock_props = MagicMock()
        mock_props.name = "secret1"
        mock_props.tags = {"environment": "production", "credential_type": "api_key"}
        mock_props.expires_on = None
        mock_props.updated_on = None
        mock_props.created_on = datetime.now(UTC)
        mock_props.enabled = True
        mock_props.content_type = None

        async def mock_run_sync(func, *args, **kwargs):
            if "list" in str(func).lower() or callable(func):
                return [mock_props]
            return func(*args, **kwargs)

        store._client = MagicMock()
        store._run_sync = mock_run_sync
        result = await store.list_credentials(environment="production")
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_list_credentials_error(self, store):
        async def mock_run_sync(func, *args, **kwargs):
            raise Exception("Azure API error")

        store._client = MagicMock()
        store._run_sync = mock_run_sync
        result = await store.list_credentials()
        assert result == []

    def test_parse_properties_basic(self, store):
        props = MagicMock()
        props.name = "my-secret"
        props.tags = {"service": "myapp"}
        props.expires_on = None
        props.updated_on = datetime.now(UTC)
        props.created_on = datetime.now(UTC) - timedelta(days=10)
        props.enabled = True
        props.content_type = "text/plain"

        result = store._parse_properties(props)
        assert result["credential_id"] == "azure:my-secret"
        assert result["service"] == "myapp"
        assert result["last_rotated"] is not None

    def test_parse_properties_no_tags(self, store):
        props = MagicMock()
        props.name = "bare-secret"
        props.tags = None
        props.expires_on = None
        props.updated_on = None
        props.created_on = None
        props.enabled = True
        props.content_type = None

        result = store._parse_properties(props)
        assert result["credential_type"] == "secret"
        assert result["service"] == "bare-secret"

    def test_parse_properties_with_expiry(self, store):
        expiry = datetime.now(UTC) + timedelta(days=7)
        props = MagicMock()
        props.name = "expiring"
        props.tags = {}
        props.expires_on = expiry
        props.updated_on = datetime.now(UTC)
        props.created_on = datetime.now(UTC)
        props.enabled = True
        props.content_type = None

        result = store._parse_properties(props)
        assert result["expires_at"] == expiry

    @pytest.mark.asyncio
    async def test_rotate_credential_success(self, store):
        mock_result = MagicMock()
        mock_result.properties = MagicMock()
        mock_result.properties.version = "abc123"

        async def mock_run_sync(func, *args, **kwargs):
            return mock_result

        store._client = MagicMock()
        store._run_sync = mock_run_sync

        result = await store.rotate_credential("azure:my-secret", "api_key")
        assert result["success"] is True
        assert result["version"] == "abc123"

    @pytest.mark.asyncio
    async def test_rotate_credential_failure(self, store):
        async def mock_run_sync(func, *args, **kwargs):
            raise Exception("Access denied")

        store._client = MagicMock()
        store._run_sync = mock_run_sync

        result = await store.rotate_credential("azure:my-secret", "api_key")
        assert result["success"] is False
        assert "Access denied" in result["message"]

    @pytest.mark.asyncio
    async def test_rotate_strips_prefix(self, store):
        mock_result = MagicMock()
        mock_result.properties = MagicMock()
        mock_result.properties.version = "v2"

        async def mock_run_sync(func, *args, **kwargs):
            return mock_result

        store._client = MagicMock()
        store._run_sync = mock_run_sync

        result = await store.rotate_credential("azure:db-cred", "database")
        assert result["service"] == "db-cred"

    def test_parse_properties_last_rotated_from_created(self, store):
        created = datetime.now(UTC) - timedelta(days=30)
        props = MagicMock()
        props.name = "old"
        props.tags = {}
        props.expires_on = None
        props.updated_on = None
        props.created_on = created
        props.enabled = True
        props.content_type = None

        result = store._parse_properties(props)
        assert result["last_rotated"] == created

    @pytest.mark.asyncio
    async def test_rotate_no_prefix(self, store):
        mock_result = MagicMock()
        mock_result.properties = MagicMock()
        mock_result.properties.version = "v1"

        async def mock_run_sync(func, *args, **kwargs):
            return mock_result

        store._client = MagicMock()
        store._run_sync = mock_run_sync

        result = await store.rotate_credential("plain-name", "secret")
        assert result["success"] is True
