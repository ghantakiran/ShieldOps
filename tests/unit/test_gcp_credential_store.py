"""Tests for GCP Secret Manager credential store (F2)."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shieldops.integrations.credentials.gcp_secrets import GCPSecretManagerStore


class TestGCPSecretManagerStore:
    @pytest.fixture
    def store(self):
        return GCPSecretManagerStore(project_id="test-project")

    def test_store_name(self, store):
        assert store.store_name == "gcp_secret_manager"

    def test_parent(self, store):
        assert store._parent == "projects/test-project"

    @pytest.mark.asyncio
    async def test_list_credentials_empty(self, store):
        mock_client = MagicMock()
        mock_client.list_secrets.return_value = []
        store._client = mock_client

        with patch.object(store, "_run_sync", new_callable=lambda: lambda: AsyncMock()) as mock_run:
            mock_run.return_value = []
            result = await store.list_credentials()
            assert result == []

    @pytest.mark.asyncio
    async def test_list_credentials_with_secrets(self, store):
        mock_secret = MagicMock()
        mock_secret.name = "projects/test-project/secrets/db-password"
        mock_secret.labels = {"credential_type": "database", "service": "postgres"}
        mock_secret.create_time = datetime.now(UTC)

        async def mock_run_sync(func, *args, **kwargs):
            if "list_secrets" in str(func):
                return [mock_secret]
            if "access_secret_version" in str(func):
                version = MagicMock()
                version.create_time = datetime.now(UTC)
                return version
            return func(*args, **kwargs)

        store._client = MagicMock()
        store._run_sync = mock_run_sync

        result = await store.list_credentials()
        assert len(result) == 1
        assert result[0]["credential_type"] == "database"
        assert result[0]["service"] == "postgres"

    @pytest.mark.asyncio
    async def test_list_credentials_with_environment(self, store):
        async def mock_run_sync(func, *args, **kwargs):
            return []

        store._client = MagicMock()
        store._run_sync = mock_run_sync
        result = await store.list_credentials(environment="production")
        assert result == []

    @pytest.mark.asyncio
    async def test_list_credentials_error(self, store):
        async def mock_run_sync(func, *args, **kwargs):
            raise Exception("GCP API error")

        store._client = MagicMock()
        store._run_sync = mock_run_sync
        result = await store.list_credentials()
        assert result == []

    @pytest.mark.asyncio
    async def test_parse_secret_with_labels(self, store):
        mock_secret = MagicMock()
        mock_secret.name = "projects/p/secrets/my-key"
        mock_secret.labels = {"credential_type": "api_key", "service": "stripe", "ttl_days": "30"}
        mock_secret.create_time = datetime.now(UTC)

        mock_version = MagicMock()
        mock_version.create_time = datetime.now(UTC) - timedelta(days=5)

        async def mock_run_sync(func, *args, **kwargs):
            return mock_version

        store._client = MagicMock()
        store._run_sync = mock_run_sync

        result = await store._parse_secret(mock_secret)
        assert result["credential_type"] == "api_key"
        assert result["service"] == "stripe"
        assert result["expires_at"] is not None

    @pytest.mark.asyncio
    async def test_parse_secret_no_labels(self, store):
        mock_secret = MagicMock()
        mock_secret.name = "projects/p/secrets/no-labels"
        mock_secret.labels = None
        mock_secret.create_time = None

        async def mock_run_sync(func, *args, **kwargs):
            raise Exception("no version")

        store._client = MagicMock()
        store._run_sync = mock_run_sync

        result = await store._parse_secret(mock_secret)
        assert result["credential_type"] == "secret"
        assert result["name"] == "no-labels"

    @pytest.mark.asyncio
    async def test_rotate_credential_success(self, store):
        mock_response = MagicMock()
        mock_response.name = "projects/p/secrets/s/versions/2"

        async def mock_run_sync(func, *args, **kwargs):
            return mock_response

        store._client = MagicMock()
        store._run_sync = mock_run_sync

        result = await store.rotate_credential("gcp:projects/p/secrets/s", "api_key")
        assert result["success"] is True
        assert "version" in result

    @pytest.mark.asyncio
    async def test_rotate_credential_failure(self, store):
        async def mock_run_sync(func, *args, **kwargs):
            raise Exception("Permission denied")

        store._client = MagicMock()
        store._run_sync = mock_run_sync

        result = await store.rotate_credential("gcp:projects/p/secrets/s", "api_key")
        assert result["success"] is False
        assert "Permission denied" in result["message"]

    @pytest.mark.asyncio
    async def test_rotate_strips_prefix(self, store):
        mock_response = MagicMock()
        mock_response.name = "v1"

        async def mock_run_sync(func, *args, **kwargs):
            return mock_response

        store._client = MagicMock()
        store._run_sync = mock_run_sync

        result = await store.rotate_credential("gcp:my-secret", "database")
        assert result["success"] is True

    def test_ensure_client(self):
        store = GCPSecretManagerStore(project_id="p")
        with patch(
            "shieldops.integrations.credentials.gcp_secrets.GCPSecretManagerStore._ensure_client"
        ) as mock:
            mock.return_value = MagicMock()
            store._ensure_client()

    @pytest.mark.asyncio
    async def test_parse_secret_ttl_expiry(self, store):
        mock_secret = MagicMock()
        mock_secret.name = "projects/p/secrets/expiring"
        mock_secret.labels = {"ttl_days": "7"}
        mock_secret.create_time = datetime.now(UTC)

        rotated = datetime.now(UTC) - timedelta(days=3)
        mock_version = MagicMock()
        mock_version.create_time = rotated

        async def mock_run_sync(func, *args, **kwargs):
            return mock_version

        store._client = MagicMock()
        store._run_sync = mock_run_sync

        result = await store._parse_secret(mock_secret)
        assert result["expires_at"] is not None
        assert result["last_rotated"] == rotated
