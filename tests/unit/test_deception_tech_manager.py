"""Tests for shieldops.operations.deception_tech_manager — DeceptionTechManager."""

from __future__ import annotations

from shieldops.operations.deception_tech_manager import (
    DeceptionAnalysis,
    DeceptionRecord,
    DeceptionReport,
    DeceptionTechManager,
    DeceptionType,
    DeploymentStatus,
    InteractionSeverity,
)


def _engine(**kw) -> DeceptionTechManager:
    return DeceptionTechManager(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_type_honeypot(self):
        assert DeceptionType.HONEYPOT == "honeypot"

    def test_type_honeytoken(self):
        assert DeceptionType.HONEYTOKEN == "honeytoken"

    def test_type_honeycred(self):
        assert DeceptionType.HONEYCRED == "honeycred"

    def test_type_honeyfile(self):
        assert DeceptionType.HONEYFILE == "honeyfile"

    def test_type_decoy_service(self):
        assert DeceptionType.DECOY_SERVICE == "decoy_service"

    def test_status_active(self):
        assert DeploymentStatus.ACTIVE == "active"

    def test_status_inactive(self):
        assert DeploymentStatus.INACTIVE == "inactive"

    def test_status_triggered(self):
        assert DeploymentStatus.TRIGGERED == "triggered"

    def test_status_maintenance(self):
        assert DeploymentStatus.MAINTENANCE == "maintenance"

    def test_status_decommissioned(self):
        assert DeploymentStatus.DECOMMISSIONED == "decommissioned"

    def test_severity_critical(self):
        assert InteractionSeverity.CRITICAL == "critical"

    def test_severity_high(self):
        assert InteractionSeverity.HIGH == "high"

    def test_severity_medium(self):
        assert InteractionSeverity.MEDIUM == "medium"

    def test_severity_low(self):
        assert InteractionSeverity.LOW == "low"

    def test_severity_benign(self):
        assert InteractionSeverity.BENIGN == "benign"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_deception_record_defaults(self):
        r = DeceptionRecord()
        assert r.id
        assert r.asset_name == ""
        assert r.deception_type == DeceptionType.HONEYPOT
        assert r.deployment_status == DeploymentStatus.ACTIVE
        assert r.interaction_severity == InteractionSeverity.CRITICAL
        assert r.detection_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_deception_analysis_defaults(self):
        c = DeceptionAnalysis()
        assert c.id
        assert c.asset_name == ""
        assert c.deception_type == DeceptionType.HONEYPOT
        assert c.analysis_score == 0.0
        assert c.threshold == 0.0
        assert c.breached is False
        assert c.description == ""
        assert c.created_at > 0

    def test_deception_report_defaults(self):
        r = DeceptionReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.low_detection_count == 0
        assert r.avg_detection_score == 0.0
        assert r.by_type == {}
        assert r.by_status == {}
        assert r.by_severity == {}
        assert r.top_low_detection == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_asset
# ---------------------------------------------------------------------------


class TestRecordAsset:
    def test_basic(self):
        eng = _engine()
        r = eng.record_asset(
            asset_name="prod-honeypot-01",
            deception_type=DeceptionType.HONEYTOKEN,
            deployment_status=DeploymentStatus.TRIGGERED,
            interaction_severity=InteractionSeverity.HIGH,
            detection_score=92.0,
            service="auth-svc",
            team="security",
        )
        assert r.asset_name == "prod-honeypot-01"
        assert r.deception_type == DeceptionType.HONEYTOKEN
        assert r.deployment_status == DeploymentStatus.TRIGGERED
        assert r.interaction_severity == InteractionSeverity.HIGH
        assert r.detection_score == 92.0
        assert r.service == "auth-svc"
        assert r.team == "security"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_asset(asset_name=f"ASSET-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_asset
# ---------------------------------------------------------------------------


class TestGetAsset:
    def test_found(self):
        eng = _engine()
        r = eng.record_asset(
            asset_name="prod-honeypot-01",
            interaction_severity=InteractionSeverity.CRITICAL,
        )
        result = eng.get_asset(r.id)
        assert result is not None
        assert result.interaction_severity == InteractionSeverity.CRITICAL

    def test_not_found(self):
        eng = _engine()
        assert eng.get_asset("nonexistent") is None


# ---------------------------------------------------------------------------
# list_assets
# ---------------------------------------------------------------------------


class TestListAssets:
    def test_list_all(self):
        eng = _engine()
        eng.record_asset(asset_name="ASSET-001")
        eng.record_asset(asset_name="ASSET-002")
        assert len(eng.list_assets()) == 2

    def test_filter_by_deception_type(self):
        eng = _engine()
        eng.record_asset(
            asset_name="ASSET-001",
            deception_type=DeceptionType.HONEYPOT,
        )
        eng.record_asset(
            asset_name="ASSET-002",
            deception_type=DeceptionType.HONEYFILE,
        )
        results = eng.list_assets(deception_type=DeceptionType.HONEYPOT)
        assert len(results) == 1

    def test_filter_by_deployment_status(self):
        eng = _engine()
        eng.record_asset(
            asset_name="ASSET-001",
            deployment_status=DeploymentStatus.ACTIVE,
        )
        eng.record_asset(
            asset_name="ASSET-002",
            deployment_status=DeploymentStatus.INACTIVE,
        )
        results = eng.list_assets(
            deployment_status=DeploymentStatus.ACTIVE,
        )
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_asset(asset_name="ASSET-001", team="security")
        eng.record_asset(asset_name="ASSET-002", team="platform")
        results = eng.list_assets(team="security")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_asset(asset_name=f"ASSET-{i}")
        assert len(eng.list_assets(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            asset_name="prod-honeypot-01",
            deception_type=DeceptionType.HONEYTOKEN,
            analysis_score=88.5,
            threshold=80.0,
            breached=True,
            description="low detection rate observed",
        )
        assert a.asset_name == "prod-honeypot-01"
        assert a.deception_type == DeceptionType.HONEYTOKEN
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(asset_name=f"ASSET-{i}")
        assert len(eng._analyses) == 2


# ---------------------------------------------------------------------------
# analyze_deception_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDeceptionDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_asset(
            asset_name="ASSET-001",
            deception_type=DeceptionType.HONEYPOT,
            detection_score=90.0,
        )
        eng.record_asset(
            asset_name="ASSET-002",
            deception_type=DeceptionType.HONEYPOT,
            detection_score=70.0,
        )
        result = eng.analyze_deception_distribution()
        assert "honeypot" in result
        assert result["honeypot"]["count"] == 2
        assert result["honeypot"]["avg_detection_score"] == 80.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_deception_distribution() == {}


# ---------------------------------------------------------------------------
# identify_low_detection_assets
# ---------------------------------------------------------------------------


class TestIdentifyLowDetectionAssets:
    def test_detects_below_threshold(self):
        eng = _engine(detection_threshold=80.0)
        eng.record_asset(asset_name="ASSET-001", detection_score=60.0)
        eng.record_asset(asset_name="ASSET-002", detection_score=90.0)
        results = eng.identify_low_detection_assets()
        assert len(results) == 1
        assert results[0]["asset_name"] == "ASSET-001"

    def test_sorted_ascending(self):
        eng = _engine(detection_threshold=80.0)
        eng.record_asset(asset_name="ASSET-001", detection_score=50.0)
        eng.record_asset(asset_name="ASSET-002", detection_score=30.0)
        results = eng.identify_low_detection_assets()
        assert len(results) == 2
        assert results[0]["detection_score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_low_detection_assets() == []


# ---------------------------------------------------------------------------
# rank_by_detection
# ---------------------------------------------------------------------------


class TestRankByDetection:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_asset(asset_name="ASSET-001", service="auth-svc", detection_score=90.0)
        eng.record_asset(asset_name="ASSET-002", service="api-gw", detection_score=50.0)
        results = eng.rank_by_detection()
        assert len(results) == 2
        assert results[0]["service"] == "api-gw"
        assert results[0]["avg_detection_score"] == 50.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_detection() == []


# ---------------------------------------------------------------------------
# detect_deception_trends
# ---------------------------------------------------------------------------


class TestDetectDeceptionTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(asset_name="ASSET-001", analysis_score=50.0)
        result = eng.detect_deception_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(asset_name="ASSET-001", analysis_score=20.0)
        eng.add_analysis(asset_name="ASSET-002", analysis_score=20.0)
        eng.add_analysis(asset_name="ASSET-003", analysis_score=80.0)
        eng.add_analysis(asset_name="ASSET-004", analysis_score=80.0)
        result = eng.detect_deception_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_deception_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(detection_threshold=80.0)
        eng.record_asset(
            asset_name="prod-honeypot-01",
            deception_type=DeceptionType.HONEYTOKEN,
            deployment_status=DeploymentStatus.TRIGGERED,
            interaction_severity=InteractionSeverity.HIGH,
            detection_score=50.0,
        )
        report = eng.generate_report()
        assert isinstance(report, DeceptionReport)
        assert report.total_records == 1
        assert report.low_detection_count == 1
        assert len(report.top_low_detection) == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "healthy" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_asset(asset_name="ASSET-001")
        eng.add_analysis(asset_name="ASSET-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_analyses"] == 0
        assert stats["type_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_asset(
            asset_name="ASSET-001",
            deception_type=DeceptionType.HONEYPOT,
            service="auth-svc",
            team="security",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "honeypot" in stats["type_distribution"]
