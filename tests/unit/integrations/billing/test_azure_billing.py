"""Tests for the Azure Cost Management billing integration.

Tests cover:
- Initialization and class attributes
- Provider name is correct
- query() returns BillingData on success (mock Cost Management client)
- query() returns empty BillingData on error
- _parse_period_days works correctly
- Row parsing with service aggregation and daily breakdown
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from shieldops.integrations.billing.azure_cost import (
    AzureCostManagementSource,
    _parse_period_days,
)
from shieldops.integrations.billing.base import BillingData

# ============================================================
# Helpers
# ============================================================


def _make_query_result(
    rows: list[list[Any]] | None = None,
) -> MagicMock:
    """Build a mock Azure Cost Management query result.

    Each row follows the Azure response format:
    ``[cost, date_str, service_name, currency]``.
    """
    result = MagicMock()
    result.rows = rows
    return result


def _mock_cost_client(
    rows: list[list[Any]] | None = None,
) -> MagicMock:
    """Build a mock CostManagementClient."""
    mock_client = MagicMock()
    mock_result = _make_query_result(rows)
    mock_client.query.usage.return_value = mock_result
    return mock_client


@pytest.fixture
def source() -> AzureCostManagementSource:
    """Standard AzureCostManagementSource for tests."""
    return AzureCostManagementSource(
        subscription_id="sub-12345",
        resource_group="my-rg",
    )


@pytest.fixture
def source_no_rg() -> AzureCostManagementSource:
    """AzureCostManagementSource without resource group."""
    return AzureCostManagementSource(
        subscription_id="sub-67890",
    )


# ============================================================
# Initialization
# ============================================================


class TestInit:
    def test_provider_name(self) -> None:
        source = AzureCostManagementSource(
            subscription_id="sub-1",
        )
        assert source.provider == "azure"

    def test_attributes_stored(
        self,
        source: AzureCostManagementSource,
    ) -> None:
        assert source._subscription_id == "sub-12345"
        assert source._resource_group == "my-rg"

    def test_resource_group_optional(
        self,
        source_no_rg: AzureCostManagementSource,
    ) -> None:
        assert source_no_rg._resource_group is None

    def test_client_initially_none(
        self,
        source: AzureCostManagementSource,
    ) -> None:
        assert source._client is None


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
        source: AzureCostManagementSource,
    ) -> None:
        # Row format: [cost, date, service, currency]
        mock_client = _mock_cost_client(
            rows=[
                [120.50, "20250101", "Virtual Machines", "USD"],
                [30.00, "20250101", "Storage", "USD"],
                [80.25, "20250102", "Virtual Machines", "USD"],
            ],
        )
        source._client = mock_client

        result = await source.query(
            environment="production",
            period="7d",
        )

        assert isinstance(result, BillingData)
        assert result.total_cost == pytest.approx(230.75)
        assert result.currency == "USD"

    @pytest.mark.asyncio
    async def test_service_aggregation(
        self,
        source: AzureCostManagementSource,
    ) -> None:
        mock_client = _mock_cost_client(
            rows=[
                [100.0, "20250101", "Virtual Machines", "USD"],
                [50.0, "20250102", "Virtual Machines", "USD"],
                [30.0, "20250101", "Storage", "USD"],
            ],
        )
        source._client = mock_client

        result = await source.query()

        # Virtual Machines should be aggregated: 100 + 50 = 150
        assert len(result.by_service) == 2
        vm_entry = next(s for s in result.by_service if s["service"] == "Virtual Machines")
        assert vm_entry["cost"] == pytest.approx(150.0)

    @pytest.mark.asyncio
    async def test_services_sorted_by_cost_desc(
        self,
        source: AzureCostManagementSource,
    ) -> None:
        mock_client = _mock_cost_client(
            rows=[
                [10.0, "20250101", "Cheap Service", "USD"],
                [500.0, "20250101", "Expensive Service", "USD"],
                [50.0, "20250101", "Mid Service", "USD"],
            ],
        )
        source._client = mock_client

        result = await source.query()

        services = [s["service"] for s in result.by_service]
        assert services == [
            "Expensive Service",
            "Mid Service",
            "Cheap Service",
        ]

    @pytest.mark.asyncio
    async def test_daily_breakdown(
        self,
        source: AzureCostManagementSource,
    ) -> None:
        mock_client = _mock_cost_client(
            rows=[
                [50.0, "20250101", "VM", "USD"],
                [60.0, "20250102", "VM", "USD"],
            ],
        )
        source._client = mock_client

        result = await source.query()

        assert len(result.daily_breakdown) == 2
        # Azure returns dates in compact YYYYMMDD format
        assert result.daily_breakdown[0]["date"] == "20250101"
        assert result.daily_breakdown[0]["cost"] == pytest.approx(
            50.0,
        )
        assert result.daily_breakdown[1]["date"] == "20250102"

    @pytest.mark.asyncio
    async def test_by_environment_matches_total(
        self,
        source: AzureCostManagementSource,
    ) -> None:
        mock_client = _mock_cost_client(
            rows=[
                [100.0, "20250101", "VM", "USD"],
            ],
        )
        source._client = mock_client

        result = await source.query(environment="staging")

        assert len(result.by_environment) == 1
        assert result.by_environment[0]["environment"] == "staging"
        assert result.by_environment[0]["cost"] == pytest.approx(
            100.0,
        )

    @pytest.mark.asyncio
    async def test_metadata_contains_provider(
        self,
        source: AzureCostManagementSource,
    ) -> None:
        mock_client = _mock_cost_client(rows=[])
        source._client = mock_client

        result = await source.query()

        assert result.metadata["provider"] == "azure"
        assert result.metadata["subscription_id"] == "sub-12345"

    @pytest.mark.asyncio
    async def test_empty_rows(
        self,
        source: AzureCostManagementSource,
    ) -> None:
        mock_client = _mock_cost_client(rows=[])
        source._client = mock_client

        result = await source.query()

        assert result.total_cost == 0.0
        assert result.by_service == []
        assert result.daily_breakdown == []

    @pytest.mark.asyncio
    async def test_none_rows(
        self,
        source: AzureCostManagementSource,
    ) -> None:
        mock_client = _mock_cost_client(rows=None)
        source._client = mock_client

        result = await source.query()

        assert result.total_cost == 0.0
        assert result.by_service == []


# ============================================================
# query() — error handling
# ============================================================


class TestQueryError:
    @pytest.mark.asyncio
    async def test_returns_empty_billing_data_on_error(
        self,
        source: AzureCostManagementSource,
    ) -> None:
        source._client = MagicMock()
        source._client.query.usage.side_effect = RuntimeError(
            "Azure unavailable",
        )

        result = await source.query()

        assert isinstance(result, BillingData)
        assert result.total_cost == 0.0
        assert "error" in result.metadata
        assert "Azure unavailable" in result.metadata["error"]

    @pytest.mark.asyncio
    async def test_error_preserves_period_dates(
        self,
        source: AzureCostManagementSource,
    ) -> None:
        source._client = MagicMock()
        source._client.query.usage.side_effect = RuntimeError(
            "fail",
        )

        result = await source.query(period="7d")

        assert result.period_start != ""
        assert result.period_end != ""
        assert result.currency == "USD"


# ============================================================
# _ensure_client
# ============================================================


class TestEnsureClient:
    def test_returns_existing_client(
        self,
        source: AzureCostManagementSource,
    ) -> None:
        existing = MagicMock()
        source._client = existing
        assert source._ensure_client() is existing


# ============================================================
# _build_query_body
# ============================================================


class TestBuildQueryBody:
    def test_query_body_structure(self) -> None:
        body = AzureCostManagementSource._build_query_body(
            "2025-01-01",
            "2025-01-31",
        )

        assert body["type"] == "ActualCost"
        assert body["timeframe"] == "Custom"
        assert body["timePeriod"]["from"] == "2025-01-01T00:00:00Z"
        assert body["timePeriod"]["to"] == "2025-01-31T23:59:59Z"
        assert body["dataset"]["granularity"] == "Daily"
        assert "totalCost" in body["dataset"]["aggregation"]
        assert len(body["dataset"]["grouping"]) == 1
        assert body["dataset"]["grouping"][0]["name"] == "ServiceName"


# ============================================================
# _parse_rows
# ============================================================


class TestParseRows:
    def test_parses_valid_rows(self) -> None:
        result = _make_query_result(
            rows=[
                [100.0, "20250101", "VM", "USD"],
                [50.0, "20250102", "Storage", "EUR"],
            ],
        )
        by_svc, daily, total, currency = AzureCostManagementSource._parse_rows(result)

        assert total == pytest.approx(150.0)
        assert "VM" in by_svc
        assert "Storage" in by_svc
        assert len(daily) == 2

    def test_parses_empty_rows(self) -> None:
        result = _make_query_result(rows=[])
        by_svc, daily, total, currency = AzureCostManagementSource._parse_rows(result)

        assert total == 0.0
        assert by_svc == {}
        assert daily == {}

    def test_parses_none_rows(self) -> None:
        result = _make_query_result(rows=None)
        by_svc, daily, total, currency = AzureCostManagementSource._parse_rows(result)

        assert total == 0.0

    def test_handles_short_rows(self) -> None:
        """Rows with fewer than 4 elements use defaults."""
        result = _make_query_result(
            rows=[[42.0]],
        )
        by_svc, daily, total, currency = AzureCostManagementSource._parse_rows(result)

        assert total == pytest.approx(42.0)
        assert "Unknown" in by_svc
        assert currency == "USD"
