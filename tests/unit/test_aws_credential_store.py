"""Tests for the AWS Secrets Manager credential store implementation.

Tests cover:
- list_credentials (with/without environment filter, empty, API error)
- rotate_credential (success, API error)
- Secret parsing with rotation metadata
- Initialization and import re-exports
"""

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import MagicMock

import pytest

from shieldops.integrations.credentials.aws_secrets import AWSSecretsManagerStore

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_secret(
    name: str = "db-password",
    arn: str = "arn:aws:secretsmanager:us-east-1:123:secret:db-password-abc",
    rotation_enabled: bool = True,
    last_rotated: datetime | None = None,
    tags: list[dict[str, str]] | None = None,
    rotation_days: int = 90,
) -> dict[str, Any]:
    """Build a mock Secrets Manager secret entry."""
    secret: dict[str, Any] = {
        "ARN": arn,
        "Name": name,
        "RotationEnabled": rotation_enabled,
        "Tags": tags
        or [
            {"Key": "Environment", "Value": "production"},
            {"Key": "Service", "Value": "api"},
            {"Key": "CredentialType", "Value": "database"},
        ],
    }
    if last_rotated:
        secret["LastRotatedDate"] = last_rotated
        secret["RotationRules"] = {"AutomaticallyAfterDays": rotation_days}
    return secret


@pytest.fixture
def store() -> AWSSecretsManagerStore:
    """Create an AWSSecretsManagerStore with mocked boto3 client."""
    s = AWSSecretsManagerStore(region="us-east-1")
    s._client = MagicMock()
    s._ensure_client = MagicMock()  # type: ignore[method-assign]
    return s


# ============================================================================
# list_credentials
# ============================================================================


class TestListCredentials:
    @pytest.mark.asyncio
    async def test_list_returns_credentials(self, store: AWSSecretsManagerStore) -> None:
        mock_paginator = MagicMock()
        pages = [
            {"SecretList": [_make_secret("db-password"), _make_secret("api-key")]},
        ]
        mock_paginator.paginate.return_value = iter(pages)
        store._client.get_paginator.return_value = mock_paginator

        credentials = await store.list_credentials()

        assert len(credentials) == 2
        assert credentials[0]["name"] == "db-password"
        assert credentials[1]["name"] == "api-key"

    @pytest.mark.asyncio
    async def test_list_empty(self, store: AWSSecretsManagerStore) -> None:
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = iter([{"SecretList": []}])
        store._client.get_paginator.return_value = mock_paginator

        credentials = await store.list_credentials()

        assert credentials == []

    @pytest.mark.asyncio
    async def test_list_api_error_returns_empty(self, store: AWSSecretsManagerStore) -> None:
        store._client.get_paginator.side_effect = Exception("AccessDenied")

        credentials = await store.list_credentials()

        assert credentials == []

    @pytest.mark.asyncio
    async def test_list_with_environment_filter(self, store: AWSSecretsManagerStore) -> None:
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = iter(
            [
                {"SecretList": [_make_secret("db-password")]},
            ]
        )
        store._client.get_paginator.return_value = mock_paginator

        credentials = await store.list_credentials(environment="production")

        assert len(credentials) == 1
        # Verify paginator was called with filter
        call_kwargs = mock_paginator.paginate.call_args
        if call_kwargs:
            filters = call_kwargs.kwargs.get("Filters", [])
            assert any(f.get("Key") == "tag-value" for f in filters)


# ============================================================================
# Secret parsing
# ============================================================================


class TestParseSecret:
    def test_parse_basic_secret(self, store: AWSSecretsManagerStore) -> None:
        secret = _make_secret("db-password")
        result = store._parse_secret(secret)

        assert result["credential_id"] == secret["ARN"]
        assert result["credential_type"] == "database"
        assert result["service"] == "api"
        assert result["name"] == "db-password"
        assert result["rotation_enabled"] is True

    def test_parse_with_rotation_date(self, store: AWSSecretsManagerStore) -> None:
        last_rotated = datetime(2024, 1, 1, tzinfo=UTC)
        secret = _make_secret("db-password", last_rotated=last_rotated, rotation_days=30)
        result = store._parse_secret(secret)

        assert result["last_rotated"] == last_rotated
        assert result["expires_at"] == last_rotated + timedelta(days=30)

    def test_parse_without_rotation(self, store: AWSSecretsManagerStore) -> None:
        secret = _make_secret("static-key", rotation_enabled=False)
        result = store._parse_secret(secret)

        assert result["rotation_enabled"] is False
        assert result["expires_at"] is None

    def test_parse_no_tags(self, store: AWSSecretsManagerStore) -> None:
        secret = {"ARN": "arn:test", "Name": "bare-secret", "Tags": []}
        result = store._parse_secret(secret)

        assert result["credential_type"] == "secret"
        assert result["service"] == "bare-secret"

    def test_parse_falls_back_to_name_for_credential_id(
        self, store: AWSSecretsManagerStore
    ) -> None:
        secret = {"Name": "my-secret", "Tags": []}
        result = store._parse_secret(secret)

        assert result["credential_id"] == "my-secret"


# ============================================================================
# rotate_credential
# ============================================================================


class TestRotateCredential:
    @pytest.mark.asyncio
    async def test_rotate_success(self, store: AWSSecretsManagerStore) -> None:
        store._client.rotate_secret.return_value = {
            "ARN": "arn:aws:secretsmanager:us-east-1:123:secret:db-pw",
            "Name": "db-password",
            "VersionId": "v2-abc123",
        }

        result = await store.rotate_credential("db-password", "database")

        assert result["success"] is True
        assert result["credential_id"] == "db-password"
        assert "v2-abc123" in result["message"]
        assert result["version_id"] == "v2-abc123"

    @pytest.mark.asyncio
    async def test_rotate_api_error(self, store: AWSSecretsManagerStore) -> None:
        store._client.rotate_secret.side_effect = Exception("ResourceNotFoundException")

        result = await store.rotate_credential("missing-secret", "api_key")

        assert result["success"] is False
        assert "ResourceNotFoundException" in result["message"]

    @pytest.mark.asyncio
    async def test_rotate_preserves_type(self, store: AWSSecretsManagerStore) -> None:
        store._client.rotate_secret.return_value = {
            "Name": "api-key",
            "VersionId": "v1",
        }

        result = await store.rotate_credential("api-key", "api_key")

        assert result["credential_type"] == "api_key"


# ============================================================================
# Initialization
# ============================================================================


class TestInit:
    def test_store_name(self) -> None:
        store = AWSSecretsManagerStore()
        assert store.store_name == "aws_secrets_manager"

    def test_default_region(self) -> None:
        store = AWSSecretsManagerStore()
        assert store._region == "us-east-1"

    def test_custom_region(self) -> None:
        store = AWSSecretsManagerStore(region="eu-west-1")
        assert store._region == "eu-west-1"

    def test_client_initially_none(self) -> None:
        store = AWSSecretsManagerStore()
        assert store._client is None

    def test_implements_credential_store(self) -> None:
        from shieldops.agents.security.protocols import CredentialStore

        assert issubclass(AWSSecretsManagerStore, CredentialStore)
