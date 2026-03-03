"""Tests for shieldops.billing.data_transfer_optimizer."""

from __future__ import annotations

from shieldops.billing.data_transfer_optimizer import (
    DataTransferOptimizer,
    DataTransferRecord,
    DataTransferReport,
    OptimizationAction,
    TransferAnalysis,
    TransferDirection,
    TransferType,
)


def _engine(**kw) -> DataTransferOptimizer:
    return DataTransferOptimizer(**kw)


class TestEnums:
    def test_transfertype_inter_region(self):
        assert TransferType.INTER_REGION == "inter_region"

    def test_transfertype_inter_az(self):
        assert TransferType.INTER_AZ == "inter_az"

    def test_transfertype_internet(self):
        assert TransferType.INTERNET == "internet"

    def test_transfertype_vpn(self):
        assert TransferType.VPN == "vpn"

    def test_transfertype_direct_connect(self):
        assert TransferType.DIRECT_CONNECT == "direct_connect"

    def test_optimizationaction_compress(self):
        assert OptimizationAction.COMPRESS == "compress"

    def test_optimizationaction_cache(self):
        assert OptimizationAction.CACHE == "cache"

    def test_optimizationaction_relocate(self):
        assert OptimizationAction.RELOCATE == "relocate"

    def test_optimizationaction_batch(self):
        assert OptimizationAction.BATCH == "batch"

    def test_optimizationaction_deduplicate(self):
        assert OptimizationAction.DEDUPLICATE == "deduplicate"

    def test_transferdirection_ingress(self):
        assert TransferDirection.INGRESS == "ingress"

    def test_transferdirection_egress(self):
        assert TransferDirection.EGRESS == "egress"

    def test_transferdirection_intra(self):
        assert TransferDirection.INTRA == "intra"

    def test_transferdirection_cross_cloud(self):
        assert TransferDirection.CROSS_CLOUD == "cross_cloud"

    def test_transferdirection_hybrid(self):
        assert TransferDirection.HYBRID == "hybrid"


class TestModels:
    def test_data_transfer_record_defaults(self):
        r = DataTransferRecord()
        assert r.id
        assert r.transfer_type == TransferType.INTERNET
        assert r.optimization_action == OptimizationAction.COMPRESS
        assert r.transfer_direction == TransferDirection.EGRESS
        assert r.transfer_gb == 0.0
        assert r.cost_before == 0.0
        assert r.cost_after == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_transfer_analysis_defaults(self):
        a = TransferAnalysis()
        assert a.id
        assert a.transfer_type == TransferType.INTERNET
        assert a.analysis_score == 0.0
        assert a.breached is False
        assert a.created_at > 0

    def test_data_transfer_report_defaults(self):
        r = DataTransferReport()
        assert r.id
        assert r.total_records == 0
        assert r.optimized_count == 0
        assert r.avg_cost_reduction == 0.0
        assert r.by_transfer_type == {}
        assert r.top_optimizations == []
        assert r.recommendations == []
        assert r.generated_at > 0


class TestRecordTransfer:
    def test_basic(self):
        eng = _engine()
        r = eng.record_transfer(
            transfer_type=TransferType.INTER_REGION,
            optimization_action=OptimizationAction.CACHE,
            transfer_direction=TransferDirection.EGRESS,
            transfer_gb=500.0,
            cost_before=200.0,
            cost_after=50.0,
            service="cdn",
            team="platform",
        )
        assert r.transfer_type == TransferType.INTER_REGION
        assert r.cost_before == 200.0
        assert r.team == "platform"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for _i in range(5):
            eng.record_transfer(transfer_type=TransferType.INTERNET)
        assert len(eng._records) == 3


class TestGetTransfer:
    def test_found(self):
        eng = _engine()
        r = eng.record_transfer(transfer_gb=100.0)
        result = eng.get_transfer(r.id)
        assert result is not None
        assert result.transfer_gb == 100.0

    def test_not_found(self):
        eng = _engine()
        assert eng.get_transfer("nonexistent") is None


class TestListTransfers:
    def test_list_all(self):
        eng = _engine()
        eng.record_transfer(transfer_type=TransferType.INTERNET)
        eng.record_transfer(transfer_type=TransferType.INTER_REGION)
        assert len(eng.list_transfers()) == 2

    def test_filter_by_type(self):
        eng = _engine()
        eng.record_transfer(transfer_type=TransferType.INTERNET)
        eng.record_transfer(transfer_type=TransferType.VPN)
        results = eng.list_transfers(transfer_type=TransferType.INTERNET)
        assert len(results) == 1

    def test_filter_by_direction(self):
        eng = _engine()
        eng.record_transfer(transfer_direction=TransferDirection.EGRESS)
        eng.record_transfer(transfer_direction=TransferDirection.INGRESS)
        results = eng.list_transfers(transfer_direction=TransferDirection.EGRESS)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_transfer(team="platform")
        eng.record_transfer(team="data")
        results = eng.list_transfers(team="platform")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for _i in range(10):
            eng.record_transfer(transfer_type=TransferType.INTERNET)
        assert len(eng.list_transfers(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            transfer_type=TransferType.INTER_REGION,
            analysis_score=75.0,
            threshold=60.0,
            breached=True,
            description="high inter-region transfer cost",
        )
        assert a.transfer_type == TransferType.INTER_REGION
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for _i in range(5):
            eng.add_analysis(transfer_type=TransferType.INTERNET)
        assert len(eng._analyses) == 2


class TestAnalyzeTypeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_transfer(transfer_type=TransferType.INTERNET, cost_before=100.0, cost_after=60.0)
        eng.record_transfer(
            transfer_type=TransferType.INTERNET, cost_before=200.0, cost_after=100.0
        )
        result = eng.analyze_type_distribution()
        assert "internet" in result
        assert result["internet"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_type_distribution() == {}


class TestIdentifyHighCostTransfers:
    def test_detects_above_threshold(self):
        eng = _engine(cost_reduction_threshold=50.0)
        eng.record_transfer(cost_before=200.0, cost_after=50.0)
        eng.record_transfer(cost_before=10.0, cost_after=5.0)
        results = eng.identify_high_cost_transfers()
        assert len(results) == 1
        assert results[0]["cost_before"] == 200.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_high_cost_transfers() == []


class TestRankByTransferCost:
    def test_sorted_descending(self):
        eng = _engine()
        eng.record_transfer(service="cdn-svc", cost_before=1000.0)
        eng.record_transfer(service="api-svc", cost_before=200.0)
        results = eng.rank_by_transfer_cost()
        assert results[0]["service"] == "cdn-svc"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_transfer_cost() == []


class TestDetectTransferTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(analysis_score=50.0)
        result = eng.detect_transfer_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(analysis_score=10.0)
        eng.add_analysis(analysis_score=10.0)
        eng.add_analysis(analysis_score=80.0)
        eng.add_analysis(analysis_score=80.0)
        result = eng.detect_transfer_trends()
        assert result["trend"] == "improving"

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_transfer_trends()
        assert result["trend"] == "insufficient_data"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_transfer(
            transfer_type=TransferType.INTER_REGION,
            optimization_action=OptimizationAction.CACHE,
            transfer_direction=TransferDirection.EGRESS,
            cost_before=500.0,
            cost_after=100.0,
        )
        report = eng.generate_report()
        assert isinstance(report, DataTransferReport)
        assert report.total_records == 1
        assert report.optimized_count == 1

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "healthy" in report.recommendations[0]


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_transfer(transfer_type=TransferType.INTERNET)
        eng.add_analysis(transfer_type=TransferType.INTERNET)
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["transfer_type_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_transfer(
            transfer_type=TransferType.INTER_REGION,
            service="cdn",
            team="platform",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert "inter_region" in stats["transfer_type_distribution"]
