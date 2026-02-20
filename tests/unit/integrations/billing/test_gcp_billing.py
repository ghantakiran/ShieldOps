"""Tests for the GCP Cloud Billing integration.

Tests cover:
- Initialization and class attributes
- Provider name is correct
- query() returns BillingData on success (mock BigQuery client)
- query() returns empty BillingData on error
- _parse_period_days works correctly
- Service cost and daily breakdown parsing
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from shieldops.integrations.billing.base import BillingData
from shieldops.integrations.billing.gcp_billing import (
    GCPBillingSource,
    _parse_period_days,
)

# ============================================================
# Helpers
# ============================================================


def _make_service_row(
    service_name: str,
    total_cost: float,
    currency: str = "USD",
) -> MagicMock:
    """Build a mock BigQuery row for service cost query."""
    row = MagicMock()
    row.service_name = service_name
    row.total_cost = total_cost
    row.currency = currency
    return row


def _make_daily_row(
    usage_date: str,
    daily_cost: float,
) -> MagicMock:
    """Build a mock BigQuery row for daily breakdown query."""
    row = MagicMock()
    row.usage_date = usage_date
    row.daily_cost = daily_cost
    return row


def _mock_bq_client(
    service_rows: list[Any] | None = None,
    daily_rows: list[Any] | None = None,
) -> MagicMock:
    """Build a mock BigQuery client.

    The client's ``query().result()`` returns the provided rows
    in sequence (first call -> service_rows, second -> daily).
    """
    if service_rows is None:
        service_rows = []
    if daily_rows is None:
        daily_rows = []

    mock_client = MagicMock()
    # Each call to client.query(sql) returns a job whose
    # .result() yields rows.
    service_job = MagicMock()
    service_job.result.return_value = service_rows

    daily_job = MagicMock()
    daily_job.result.return_value = daily_rows

    mock_client.query.side_effect = [service_job, daily_job]
    return mock_client


@pytest.fixture
def source() -> GCPBillingSource:
    """Standard GCPBillingSource for tests."""
    return GCPBillingSource(
        project_id="my-project",
        dataset="billing_export",
        table="gcp_billing_export_v1",
    )


# ============================================================
# Initialization
# ============================================================


class TestInit:
    def test_provider_name(self) -> None:
        source = GCPBillingSource(project_id="p")
        assert source.provider == "gcp"

    def test_attributes_stored(self) -> None:
        source = GCPBillingSource(
            project_id="proj-123",
            dataset="custom_ds",
            table="custom_table",
        )
        assert source._project_id == "proj-123"
        assert source._dataset == "custom_ds"
        assert source._table == "custom_table"

    def test_client_initially_none(self) -> None:
        source = GCPBillingSource(project_id="p")
        assert source._client is None

    def test_default_dataset_and_table(self) -> None:
        source = GCPBillingSource(project_id="p")
        assert source._dataset == "billing_export"
        assert source._table == "gcp_billing_export_v1"


# ============================================================
# _parse_period_days
# ============================================================


class TestParsePeriodDays:
    def test_valid_period(self) -> None:
        assert _parse_period_days("7d") == 7
        assert _parse_period_days("30d") == 30
        assert _parse_period_days("90d") == 90

    def test_invalid_period_falls_back(self) -> None:
        assert _parse_period_days("invalid") == 30
        assert _parse_period_days("") == 30
        assert _parse_period_days("30") == 30

    def test_zero_days(self) -> None:
        assert _parse_period_days("0d") == 0

    def test_large_period(self) -> None:
        assert _parse_period_days("365d") == 365


# ============================================================
# query() — success
# ============================================================


class TestQuerySuccess:
    @pytest.mark.asyncio
    async def test_returns_billing_data(
        self,
        source: GCPBillingSource,
    ) -> None:
        mock_client = _mock_bq_client(
            service_rows=[
                _make_service_row("Compute Engine", 150.50),
                _make_service_row("Cloud Storage", 25.00),
            ],
            daily_rows=[
                _make_daily_row("2025-01-01", 6.0),
                _make_daily_row("2025-01-02", 5.5),
            ],
        )
        source._client = mock_client

        result = await source.query(
            environment="staging",
            period="7d",
        )

        assert isinstance(result, BillingData)
        assert result.total_cost == pytest.approx(175.50)
        assert result.currency == "USD"
        assert len(result.by_service) == 2
        assert result.by_service[0]["service"] == "Compute Engine"
        assert result.by_service[0]["cost"] == pytest.approx(
            150.50,
        )
        assert len(result.daily_breakdown) == 2
        assert result.daily_breakdown[0]["date"] == "2025-01-01"

    @pytest.mark.asyncio
    async def test_by_environment_matches_total(
        self,
        source: GCPBillingSource,
    ) -> None:
        mock_client = _mock_bq_client(
            service_rows=[
                _make_service_row("BigQuery", 100.0),
            ],
            daily_rows=[],
        )
        source._client = mock_client

        result = await source.query(environment="production")

        assert len(result.by_environment) == 1
        assert result.by_environment[0]["environment"] == "production"
        assert result.by_environment[0]["cost"] == pytest.approx(
            100.0,
        )

    @pytest.mark.asyncio
    async def test_metadata_contains_provider(
        self,
        source: GCPBillingSource,
    ) -> None:
        mock_client = _mock_bq_client()
        source._client = mock_client

        result = await source.query()

        assert result.metadata["provider"] == "gcp"
        assert result.metadata["project_id"] == "my-project"

    @pytest.mark.asyncio
    async def test_empty_results(
        self,
        source: GCPBillingSource,
    ) -> None:
        mock_client = _mock_bq_client(
            service_rows=[],
            daily_rows=[],
        )
        source._client = mock_client

        result = await source.query()

        assert result.total_cost == 0.0
        assert result.by_service == []
        assert result.daily_breakdown == []


# ============================================================
# query() — error handling
# ============================================================


class TestQueryError:
    @pytest.mark.asyncio
    async def test_returns_empty_billing_data_on_error(
        self,
        source: GCPBillingSource,
    ) -> None:
        source._client = MagicMock()
        source._client.query.side_effect = RuntimeError(
            "BigQuery unavailable",
        )

        result = await source.query()

        assert isinstance(result, BillingData)
        assert result.total_cost == 0.0
        assert "error" in result.metadata
        assert "BigQuery unavailable" in result.metadata["error"]

    @pytest.mark.asyncio
    async def test_error_preserves_period_dates(
        self,
        source: GCPBillingSource,
    ) -> None:
        source._client = MagicMock()
        source._client.query.side_effect = RuntimeError("fail")

        result = await source.query(period="7d")

        assert result.period_start != ""
        assert result.period_end != ""
        assert result.currency == "USD"


# ============================================================
# _ensure_client
# ============================================================


class TestEnsureClient:
    def test_idempotent_when_set(
        self,
        source: GCPBillingSource,
    ) -> None:
        """Once a client is assigned, _ensure_client returns it."""
        mock_client = MagicMock()
        source._client = mock_client
        assert source._ensure_client() is mock_client

    def test_returns_existing_client(
        self,
        source: GCPBillingSource,
    ) -> None:
        existing = MagicMock()
        source._client = existing
        assert source._ensure_client() is existing
