"""Tests for the AWS Cost Explorer billing source implementation.

Tests cover:
- BillingData dataclass creation and defaults
- BillingSource protocol conformance
- AWSCostExplorerSource.query with mocked boto3 client
- Period parsing (7d, 30d, 90d, invalid)
- Service breakdown parsing and sorting
- Daily breakdown parsing
- Total cost calculation across multiple result groups
- Error handling (returns empty BillingData with error metadata)
- Lazy client initialisation
- Metadata population
"""

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from shieldops.integrations.billing.aws_cost_explorer import (
    AWSCostExplorerSource,
    _parse_period_days,
)
from shieldops.integrations.billing.base import BillingData, BillingSource

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_service_response(
    services: list[tuple[str, float]],
    currency: str = "USD",
) -> dict[str, Any]:
    """Build a mock GetCostAndUsage response grouped by service."""
    groups = [
        {
            "Keys": [name],
            "Metrics": {
                "UnblendedCost": {"Amount": str(cost), "Unit": currency},
                "UsageQuantity": {"Amount": "100", "Unit": "N/A"},
            },
        }
        for name, cost in services
    ]
    return {
        "ResultsByTime": [
            {
                "TimePeriod": {"Start": "2026-01-01", "End": "2026-02-01"},
                "Groups": groups,
            }
        ],
    }


def _make_daily_response(
    daily_costs: list[tuple[str, float]],
) -> dict[str, Any]:
    """Build a mock GetCostAndUsage DAILY response."""
    results = [
        {
            "TimePeriod": {"Start": date, "End": date},
            "Total": {
                "UnblendedCost": {"Amount": str(cost), "Unit": "USD"},
            },
        }
        for date, cost in daily_costs
    ]
    return {"ResultsByTime": results}


@pytest.fixture
def source() -> AWSCostExplorerSource:
    """Create an AWSCostExplorerSource with a mocked boto3 client."""
    s = AWSCostExplorerSource(region="us-west-2")
    s._client = MagicMock()
    return s


# ============================================================================
# BillingData dataclass
# ============================================================================


class TestBillingData:
    def test_creation_with_defaults(self) -> None:
        data = BillingData(total_cost=123.45)

        assert data.total_cost == 123.45
        assert data.currency == "USD"
        assert data.period_start == ""
        assert data.period_end == ""
        assert data.by_service == []
        assert data.by_environment == []
        assert data.daily_breakdown == []
        assert data.metadata == {}

    def test_creation_with_all_fields(self) -> None:
        data = BillingData(
            total_cost=500.0,
            currency="EUR",
            period_start="2026-01-01",
            period_end="2026-01-31",
            by_service=[{"service": "EC2", "cost": 300.0}],
            by_environment=[{"env": "prod", "cost": 500.0}],
            daily_breakdown=[{"date": "2026-01-01", "cost": 16.13}],
            metadata={"provider": "aws"},
        )

        assert data.total_cost == 500.0
        assert data.currency == "EUR"
        assert data.period_start == "2026-01-01"
        assert data.period_end == "2026-01-31"
        assert len(data.by_service) == 1
        assert len(data.by_environment) == 1
        assert len(data.daily_breakdown) == 1
        assert data.metadata["provider"] == "aws"

    def test_mutable_default_isolation(self) -> None:
        """Each instance must get its own default lists/dicts."""
        a = BillingData(total_cost=0.0)
        b = BillingData(total_cost=0.0)
        a.by_service.append({"service": "S3", "cost": 10.0})

        assert b.by_service == []
        assert a.metadata is not b.metadata


# ============================================================================
# BillingSource protocol
# ============================================================================


class TestBillingSourceProtocol:
    def test_aws_source_satisfies_protocol(self) -> None:
        assert isinstance(AWSCostExplorerSource(), BillingSource)

    def test_protocol_is_runtime_checkable(self) -> None:
        # Protocols with non-method members (provider) don't support
        # issubclass, so we verify via isinstance on an instance.
        assert isinstance(AWSCostExplorerSource(), BillingSource)

    def test_provider_attribute(self) -> None:
        source = AWSCostExplorerSource()
        assert source.provider == "aws"


# ============================================================================
# Period parsing
# ============================================================================


class TestParsePeriodDays:
    def test_7d(self) -> None:
        assert _parse_period_days("7d") == 7

    def test_30d(self) -> None:
        assert _parse_period_days("30d") == 30

    def test_90d(self) -> None:
        assert _parse_period_days("90d") == 90

    def test_1d(self) -> None:
        assert _parse_period_days("1d") == 1

    def test_invalid_format_defaults_to_30(self) -> None:
        assert _parse_period_days("monthly") == 30

    def test_empty_string_defaults_to_30(self) -> None:
        assert _parse_period_days("") == 30

    def test_no_suffix_defaults_to_30(self) -> None:
        assert _parse_period_days("30") == 30


# ============================================================================
# Lazy client initialisation
# ============================================================================


class TestClientInitialisation:
    def test_client_initially_none(self) -> None:
        s = AWSCostExplorerSource()
        assert s._client is None

    def test_default_region(self) -> None:
        s = AWSCostExplorerSource()
        assert s._region == "us-east-1"

    def test_custom_region(self) -> None:
        s = AWSCostExplorerSource(region="eu-west-1")
        assert s._region == "eu-west-1"

    @patch("boto3.client")
    def test_ensure_client_creates_ce_client(self, mock_client: MagicMock) -> None:
        s = AWSCostExplorerSource(region="ap-southeast-1")
        s._ensure_client()

        mock_client.assert_called_once_with("ce", region_name="us-east-1")
        assert s._client is mock_client.return_value

    @patch("boto3.client")
    def test_ensure_client_is_idempotent(self, mock_client: MagicMock) -> None:
        s = AWSCostExplorerSource()
        s._ensure_client()
        s._ensure_client()

        assert mock_client.call_count == 1


# ============================================================================
# AWSCostExplorerSource.query — service breakdown
# ============================================================================


class TestQueryServiceBreakdown:
    @pytest.mark.asyncio
    async def test_parses_service_costs(self, source: AWSCostExplorerSource) -> None:
        source._client.get_cost_and_usage.side_effect = [
            _make_service_response(
                [
                    ("Amazon EC2", 150.0),
                    ("Amazon S3", 50.0),
                    ("Amazon RDS", 100.0),
                ]
            ),
            _make_daily_response([("2026-01-15", 10.0)]),
        ]

        result = await source.query(period="30d")

        assert len(result.by_service) == 3
        # Sorted descending by cost
        assert result.by_service[0]["service"] == "Amazon EC2"
        assert result.by_service[0]["cost"] == 150.0
        assert result.by_service[1]["service"] == "Amazon RDS"
        assert result.by_service[1]["cost"] == 100.0
        assert result.by_service[2]["service"] == "Amazon S3"
        assert result.by_service[2]["cost"] == 50.0

    @pytest.mark.asyncio
    async def test_empty_service_response(self, source: AWSCostExplorerSource) -> None:
        source._client.get_cost_and_usage.side_effect = [
            {"ResultsByTime": [{"Groups": []}]},
            _make_daily_response([]),
        ]

        result = await source.query()

        assert result.by_service == []
        assert result.total_cost == 0.0

    @pytest.mark.asyncio
    async def test_sorts_by_cost_descending(self, source: AWSCostExplorerSource) -> None:
        source._client.get_cost_and_usage.side_effect = [
            _make_service_response(
                [
                    ("S3", 10.0),
                    ("EC2", 500.0),
                    ("Lambda", 200.0),
                ]
            ),
            _make_daily_response([]),
        ]

        result = await source.query()

        costs = [s["cost"] for s in result.by_service]
        assert costs == sorted(costs, reverse=True)


# ============================================================================
# AWSCostExplorerSource.query — daily breakdown
# ============================================================================


class TestQueryDailyBreakdown:
    @pytest.mark.asyncio
    async def test_parses_daily_costs(self, source: AWSCostExplorerSource) -> None:
        source._client.get_cost_and_usage.side_effect = [
            _make_service_response([("EC2", 300.0)]),
            _make_daily_response(
                [
                    ("2026-01-01", 10.5),
                    ("2026-01-02", 11.0),
                    ("2026-01-03", 9.75),
                ]
            ),
        ]

        result = await source.query()

        assert len(result.daily_breakdown) == 3
        assert result.daily_breakdown[0] == {"date": "2026-01-01", "cost": 10.5}
        assert result.daily_breakdown[1] == {"date": "2026-01-02", "cost": 11.0}
        assert result.daily_breakdown[2] == {"date": "2026-01-03", "cost": 9.75}

    @pytest.mark.asyncio
    async def test_empty_daily_response(self, source: AWSCostExplorerSource) -> None:
        source._client.get_cost_and_usage.side_effect = [
            _make_service_response([("EC2", 100.0)]),
            {"ResultsByTime": []},
        ]

        result = await source.query()

        assert result.daily_breakdown == []


# ============================================================================
# AWSCostExplorerSource.query — total cost and metadata
# ============================================================================


class TestQueryTotalCostAndMetadata:
    @pytest.mark.asyncio
    async def test_total_cost_sums_services(self, source: AWSCostExplorerSource) -> None:
        source._client.get_cost_and_usage.side_effect = [
            _make_service_response(
                [
                    ("EC2", 100.55),
                    ("S3", 200.45),
                ]
            ),
            _make_daily_response([]),
        ]

        result = await source.query()

        assert result.total_cost == 301.0

    @pytest.mark.asyncio
    async def test_total_cost_across_multiple_time_groups(
        self, source: AWSCostExplorerSource
    ) -> None:
        """When the period spans multiple months, ResultsByTime has
        multiple entries."""
        response = {
            "ResultsByTime": [
                {
                    "Groups": [
                        {
                            "Keys": ["EC2"],
                            "Metrics": {
                                "UnblendedCost": {
                                    "Amount": "100.0",
                                    "Unit": "USD",
                                },
                                "UsageQuantity": {
                                    "Amount": "50",
                                    "Unit": "N/A",
                                },
                            },
                        }
                    ]
                },
                {
                    "Groups": [
                        {
                            "Keys": ["EC2"],
                            "Metrics": {
                                "UnblendedCost": {
                                    "Amount": "200.0",
                                    "Unit": "USD",
                                },
                                "UsageQuantity": {
                                    "Amount": "80",
                                    "Unit": "N/A",
                                },
                            },
                        }
                    ]
                },
            ]
        }
        source._client.get_cost_and_usage.side_effect = [
            response,
            _make_daily_response([]),
        ]

        result = await source.query(period="90d")

        assert result.total_cost == 300.0

    @pytest.mark.asyncio
    async def test_currency_from_response(self, source: AWSCostExplorerSource) -> None:
        source._client.get_cost_and_usage.side_effect = [
            _make_service_response([("EC2", 50.0)], currency="EUR"),
            _make_daily_response([]),
        ]

        result = await source.query()

        assert result.currency == "EUR"

    @pytest.mark.asyncio
    async def test_metadata_includes_provider_and_region(
        self, source: AWSCostExplorerSource
    ) -> None:
        source._client.get_cost_and_usage.side_effect = [
            _make_service_response([("EC2", 50.0)]),
            _make_daily_response([]),
        ]

        result = await source.query(environment="staging")

        assert result.metadata["provider"] == "aws"
        assert result.metadata["region"] == "us-west-2"
        assert result.metadata["environment"] == "staging"

    @pytest.mark.asyncio
    async def test_period_dates_are_set(self, source: AWSCostExplorerSource) -> None:
        source._client.get_cost_and_usage.side_effect = [
            _make_service_response([("EC2", 10.0)]),
            _make_daily_response([]),
        ]

        result = await source.query(period="7d")

        today = datetime.now(UTC).date()
        expected_start = (today - timedelta(days=7)).isoformat()
        expected_end = today.isoformat()
        assert result.period_start == expected_start
        assert result.period_end == expected_end


# ============================================================================
# AWSCostExplorerSource.query — API call verification
# ============================================================================


class TestQueryAPICalls:
    @pytest.mark.asyncio
    async def test_calls_get_cost_and_usage_twice(self, source: AWSCostExplorerSource) -> None:
        """First call for service grouping, second for daily breakdown."""
        source._client.get_cost_and_usage.side_effect = [
            _make_service_response([("EC2", 100.0)]),
            _make_daily_response([("2026-01-01", 3.33)]),
        ]

        await source.query(period="30d")

        assert source._client.get_cost_and_usage.call_count == 2

        # First call — MONTHLY with SERVICE grouping
        first_call = source._client.get_cost_and_usage.call_args_list[0]
        assert first_call.kwargs["Granularity"] == "MONTHLY"
        assert first_call.kwargs["GroupBy"] == [{"Type": "DIMENSION", "Key": "SERVICE"}]

        # Second call — DAILY without grouping
        second_call = source._client.get_cost_and_usage.call_args_list[1]
        assert second_call.kwargs["Granularity"] == "DAILY"
        assert "GroupBy" not in second_call.kwargs

    @pytest.mark.asyncio
    async def test_time_period_uses_correct_dates(self, source: AWSCostExplorerSource) -> None:
        source._client.get_cost_and_usage.side_effect = [
            _make_service_response([]),
            _make_daily_response([]),
        ]

        await source.query(period="7d")

        today = datetime.now(UTC).date()
        start = (today - timedelta(days=7)).isoformat()
        end = today.isoformat()

        first_call = source._client.get_cost_and_usage.call_args_list[0]
        assert first_call.kwargs["TimePeriod"] == {
            "Start": start,
            "End": end,
        }


# ============================================================================
# AWSCostExplorerSource.query — error handling
# ============================================================================


class TestQueryErrorHandling:
    @pytest.mark.asyncio
    async def test_api_error_returns_empty_billing_data(
        self, source: AWSCostExplorerSource
    ) -> None:
        source._client.get_cost_and_usage.side_effect = Exception("AccessDeniedException")

        result = await source.query()

        assert isinstance(result, BillingData)
        assert result.total_cost == 0.0
        assert result.by_service == []
        assert result.daily_breakdown == []
        assert "error" in result.metadata
        assert "AccessDeniedException" in result.metadata["error"]
        assert result.metadata["provider"] == "aws"

    @pytest.mark.asyncio
    async def test_daily_breakdown_error_still_returns_error(
        self, source: AWSCostExplorerSource
    ) -> None:
        """If the first call succeeds but the daily call fails, the
        entire query returns an error result."""
        source._client.get_cost_and_usage.side_effect = [
            _make_service_response([("EC2", 100.0)]),
            Exception("ThrottlingException"),
        ]

        result = await source.query()

        assert result.total_cost == 0.0
        assert "ThrottlingException" in result.metadata["error"]

    @pytest.mark.asyncio
    async def test_ensure_client_error_returns_empty(self) -> None:
        """If boto3 import or client creation fails, query degrades."""
        s = AWSCostExplorerSource()
        s._ensure_client = MagicMock(  # type: ignore[method-assign]
            side_effect=ImportError("No module named 'boto3'")
        )

        result = await s.query()

        assert result.total_cost == 0.0
        assert "boto3" in result.metadata["error"]
