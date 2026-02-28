"""Tests for shieldops.billing.cloud_arbitrage — CloudCostArbitrageAnalyzer."""

from __future__ import annotations

from shieldops.billing.cloud_arbitrage import (
    ArbitrageRecord,
    CloudArbitrageReport,
    CloudCostArbitrageAnalyzer,
    CloudProvider,
    MigrationOpportunity,
    SavingsConfidence,
    WorkloadType,
)


def _engine(**kw) -> CloudCostArbitrageAnalyzer:
    return CloudCostArbitrageAnalyzer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    # CloudProvider (5)
    def test_provider_aws(self):
        assert CloudProvider.AWS == "aws"

    def test_provider_gcp(self):
        assert CloudProvider.GCP == "gcp"

    def test_provider_azure(self):
        assert CloudProvider.AZURE == "azure"

    def test_provider_on_prem(self):
        assert CloudProvider.ON_PREM == "on_prem"

    def test_provider_hybrid(self):
        assert CloudProvider.HYBRID == "hybrid"

    # WorkloadType (5)
    def test_workload_compute(self):
        assert WorkloadType.COMPUTE == "compute"

    def test_workload_storage(self):
        assert WorkloadType.STORAGE == "storage"

    def test_workload_database(self):
        assert WorkloadType.DATABASE == "database"

    def test_workload_networking(self):
        assert WorkloadType.NETWORKING == "networking"

    def test_workload_ml_training(self):
        assert WorkloadType.ML_TRAINING == "ml_training"

    # SavingsConfidence (5)
    def test_confidence_high(self):
        assert SavingsConfidence.HIGH == "high"

    def test_confidence_moderate(self):
        assert SavingsConfidence.MODERATE == "moderate"

    def test_confidence_low(self):
        assert SavingsConfidence.LOW == "low"

    def test_confidence_speculative(self):
        assert SavingsConfidence.SPECULATIVE == "speculative"

    def test_confidence_no_savings(self):
        assert SavingsConfidence.NO_SAVINGS == "no_savings"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_arbitrage_record_defaults(self):
        r = ArbitrageRecord()
        assert r.id
        assert r.service_name == ""
        assert r.current_provider == CloudProvider.AWS
        assert r.workload_type == WorkloadType.COMPUTE
        assert r.savings_pct == 0.0
        assert r.details == ""
        assert r.created_at > 0

    def test_migration_opportunity_defaults(self):
        o = MigrationOpportunity()
        assert o.id
        assert o.opportunity_name == ""
        assert o.target_provider == CloudProvider.GCP
        assert o.workload_type == WorkloadType.COMPUTE
        assert o.estimated_savings_usd == 0.0
        assert o.description == ""
        assert o.created_at > 0

    def test_report_defaults(self):
        r = CloudArbitrageReport()
        assert r.total_records == 0
        assert r.total_opportunities == 0
        assert r.avg_savings_pct == 0.0
        assert r.by_provider == {}
        assert r.by_workload == {}
        assert r.high_savings_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# ---------------------------------------------------------------------------
# record_arbitrage
# ---------------------------------------------------------------------------


class TestRecordArbitrage:
    def test_basic(self):
        eng = _engine()
        r = eng.record_arbitrage(
            "web-api",
            current_provider=CloudProvider.AWS,
            workload_type=WorkloadType.COMPUTE,
            savings_pct=25.0,
        )
        assert r.service_name == "web-api"
        assert r.savings_pct == 25.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_arbitrage(f"svc-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_arbitrage
# ---------------------------------------------------------------------------


class TestGetArbitrage:
    def test_found(self):
        eng = _engine()
        r = eng.record_arbitrage("web-api")
        assert eng.get_arbitrage(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_arbitrage("nonexistent") is None


# ---------------------------------------------------------------------------
# list_arbitrages
# ---------------------------------------------------------------------------


class TestListArbitrages:
    def test_list_all(self):
        eng = _engine()
        eng.record_arbitrage("svc-a")
        eng.record_arbitrage("svc-b")
        assert len(eng.list_arbitrages()) == 2

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_arbitrage("svc-a")
        eng.record_arbitrage("svc-b")
        results = eng.list_arbitrages(service_name="svc-a")
        assert len(results) == 1

    def test_filter_by_provider(self):
        eng = _engine()
        eng.record_arbitrage("s1", current_provider=CloudProvider.AWS)
        eng.record_arbitrage("s2", current_provider=CloudProvider.GCP)
        results = eng.list_arbitrages(current_provider=CloudProvider.AWS)
        assert len(results) == 1


# ---------------------------------------------------------------------------
# add_opportunity
# ---------------------------------------------------------------------------


class TestAddOpportunity:
    def test_basic(self):
        eng = _engine()
        o = eng.add_opportunity(
            "migrate-to-gcp",
            target_provider=CloudProvider.GCP,
            estimated_savings_usd=5000.0,
        )
        assert o.opportunity_name == "migrate-to-gcp"
        assert o.estimated_savings_usd == 5000.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_opportunity(f"opp-{i}")
        assert len(eng._opportunities) == 2


# ---------------------------------------------------------------------------
# analyze_savings_potential
# ---------------------------------------------------------------------------


class TestAnalyzeSavingsPotential:
    def test_with_data(self):
        eng = _engine(min_savings_pct=15.0)
        eng.record_arbitrage("web-api", savings_pct=25.0)
        eng.record_arbitrage("web-api", savings_pct=35.0)
        result = eng.analyze_savings_potential("web-api")
        assert result["service_name"] == "web-api"
        assert result["avg_savings_pct"] == 30.0
        assert result["meets_threshold"] is True

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_savings_potential("ghost")
        assert result["status"] == "no_data"


# ---------------------------------------------------------------------------
# identify_high_savings_services
# ---------------------------------------------------------------------------


class TestIdentifyHighSavingsServices:
    def test_with_high(self):
        eng = _engine(min_savings_pct=15.0)
        eng.record_arbitrage("svc-a", savings_pct=20.0)
        eng.record_arbitrage("svc-a", savings_pct=25.0)
        eng.record_arbitrage("svc-b", savings_pct=5.0)
        results = eng.identify_high_savings_services()
        assert len(results) == 1
        assert results[0]["service_name"] == "svc-a"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_high_savings_services() == []


# ---------------------------------------------------------------------------
# rank_by_savings
# ---------------------------------------------------------------------------


class TestRankBySavings:
    def test_with_data(self):
        eng = _engine()
        eng.record_arbitrage("svc-a", savings_pct=10.0)
        eng.record_arbitrage("svc-b", savings_pct=40.0)
        results = eng.rank_by_savings()
        assert results[0]["service_name"] == "svc-b"
        assert results[0]["avg_savings_pct"] == 40.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_savings() == []


# ---------------------------------------------------------------------------
# detect_arbitrage_trends
# ---------------------------------------------------------------------------


class TestDetectArbitrageTrends:
    def test_with_enough_data(self):
        eng = _engine()
        eng.record_arbitrage("svc-a", savings_pct=10.0)
        eng.record_arbitrage("svc-a", savings_pct=12.0)
        eng.record_arbitrage("svc-a", savings_pct=30.0)
        eng.record_arbitrage("svc-a", savings_pct=35.0)
        results = eng.detect_arbitrage_trends()
        assert len(results) == 1
        assert results[0]["service_name"] == "svc-a"

    def test_insufficient_data(self):
        eng = _engine()
        eng.record_arbitrage("svc-a", savings_pct=10.0)
        eng.record_arbitrage("svc-a", savings_pct=12.0)
        results = eng.detect_arbitrage_trends()
        assert len(results) == 0


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine(min_savings_pct=15.0)
        eng.record_arbitrage("svc-a", savings_pct=25.0)
        eng.add_opportunity("migrate-to-gcp")
        report = eng.generate_report()
        assert isinstance(report, CloudArbitrageReport)
        assert report.total_records == 1
        assert report.total_opportunities == 1
        assert report.high_savings_count == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "meets savings targets" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_arbitrage("svc-a")
        eng.add_opportunity("opp-a")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._opportunities) == 0


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_opportunities"] == 0
        assert stats["provider_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_arbitrage("svc-a", current_provider=CloudProvider.AWS)
        eng.record_arbitrage("svc-b", current_provider=CloudProvider.GCP)
        eng.add_opportunity("opp-a")
        stats = eng.get_stats()
        assert stats["total_records"] == 2
        assert stats["total_opportunities"] == 1
        assert stats["unique_services"] == 2
