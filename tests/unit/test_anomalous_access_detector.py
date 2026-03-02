"""Tests for shieldops.security.anomalous_access_detector — AnomalousAccessDetector."""

from __future__ import annotations

from shieldops.security.anomalous_access_detector import (
    AccessAnalysis,
    AccessRecord,
    AccessReport,
    AccessType,
    AnomalousAccessDetector,
    DetectionMethod,
    RiskLevel,
)


def _engine(**kw) -> AnomalousAccessDetector:
    return AnomalousAccessDetector(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_type_impossible_travel(self):
        assert AccessType.IMPOSSIBLE_TRAVEL == "impossible_travel"

    def test_type_unusual_hours(self):
        assert AccessType.UNUSUAL_HOURS == "unusual_hours"

    def test_type_new_location(self):
        assert AccessType.NEW_LOCATION == "new_location"

    def test_type_privilege_abuse(self):
        assert AccessType.PRIVILEGE_ABUSE == "privilege_abuse"

    def test_type_lateral_movement(self):
        assert AccessType.LATERAL_MOVEMENT == "lateral_movement"

    def test_risk_critical(self):
        assert RiskLevel.CRITICAL == "critical"

    def test_risk_high(self):
        assert RiskLevel.HIGH == "high"

    def test_risk_medium(self):
        assert RiskLevel.MEDIUM == "medium"

    def test_risk_low(self):
        assert RiskLevel.LOW == "low"

    def test_risk_negligible(self):
        assert RiskLevel.NEGLIGIBLE == "negligible"

    def test_method_rule_based(self):
        assert DetectionMethod.RULE_BASED == "rule_based"

    def test_method_ml_based(self):
        assert DetectionMethod.ML_BASED == "ml_based"

    def test_method_behavioral(self):
        assert DetectionMethod.BEHAVIORAL == "behavioral"

    def test_method_statistical(self):
        assert DetectionMethod.STATISTICAL == "statistical"

    def test_method_hybrid(self):
        assert DetectionMethod.HYBRID == "hybrid"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_access_record_defaults(self):
        r = AccessRecord()
        assert r.id
        assert r.access_name == ""
        assert r.access_type == AccessType.IMPOSSIBLE_TRAVEL
        assert r.risk_level == RiskLevel.CRITICAL
        assert r.detection_method == DetectionMethod.RULE_BASED
        assert r.anomaly_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_access_analysis_defaults(self):
        c = AccessAnalysis()
        assert c.id
        assert c.access_name == ""
        assert c.access_type == AccessType.IMPOSSIBLE_TRAVEL
        assert c.analysis_score == 0.0
        assert c.threshold == 0.0
        assert c.breached is False
        assert c.description == ""
        assert c.created_at > 0

    def test_access_report_defaults(self):
        r = AccessReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.high_anomaly_count == 0
        assert r.avg_anomaly_score == 0.0
        assert r.by_type == {}
        assert r.by_risk == {}
        assert r.by_method == {}
        assert r.top_high_anomaly == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_access
# ---------------------------------------------------------------------------


class TestRecordAccess:
    def test_basic(self):
        eng = _engine()
        r = eng.record_access(
            access_name="acc-001",
            access_type=AccessType.UNUSUAL_HOURS,
            risk_level=RiskLevel.HIGH,
            detection_method=DetectionMethod.ML_BASED,
            anomaly_score=92.0,
            service="auth-svc",
            team="security",
        )
        assert r.access_name == "acc-001"
        assert r.access_type == AccessType.UNUSUAL_HOURS
        assert r.risk_level == RiskLevel.HIGH
        assert r.detection_method == DetectionMethod.ML_BASED
        assert r.anomaly_score == 92.0
        assert r.service == "auth-svc"
        assert r.team == "security"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_access(access_name=f"acc-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_access
# ---------------------------------------------------------------------------


class TestGetAccess:
    def test_found(self):
        eng = _engine()
        r = eng.record_access(
            access_name="acc-001",
            risk_level=RiskLevel.CRITICAL,
        )
        result = eng.get_access(r.id)
        assert result is not None
        assert result.risk_level == RiskLevel.CRITICAL

    def test_not_found(self):
        eng = _engine()
        assert eng.get_access("nonexistent") is None


# ---------------------------------------------------------------------------
# list_accesses
# ---------------------------------------------------------------------------


class TestListAccesses:
    def test_list_all(self):
        eng = _engine()
        eng.record_access(access_name="acc-001")
        eng.record_access(access_name="acc-002")
        assert len(eng.list_accesses()) == 2

    def test_filter_by_access_type(self):
        eng = _engine()
        eng.record_access(
            access_name="acc-001",
            access_type=AccessType.IMPOSSIBLE_TRAVEL,
        )
        eng.record_access(
            access_name="acc-002",
            access_type=AccessType.UNUSUAL_HOURS,
        )
        results = eng.list_accesses(access_type=AccessType.IMPOSSIBLE_TRAVEL)
        assert len(results) == 1

    def test_filter_by_risk_level(self):
        eng = _engine()
        eng.record_access(
            access_name="acc-001",
            risk_level=RiskLevel.CRITICAL,
        )
        eng.record_access(
            access_name="acc-002",
            risk_level=RiskLevel.LOW,
        )
        results = eng.list_accesses(risk_level=RiskLevel.CRITICAL)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_access(access_name="acc-001", team="security")
        eng.record_access(access_name="acc-002", team="platform")
        results = eng.list_accesses(team="security")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_access(access_name=f"acc-{i}")
        assert len(eng.list_accesses(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            access_name="acc-001",
            access_type=AccessType.UNUSUAL_HOURS,
            analysis_score=88.5,
            threshold=80.0,
            breached=True,
            description="high anomaly detected",
        )
        assert a.access_name == "acc-001"
        assert a.access_type == AccessType.UNUSUAL_HOURS
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(access_name=f"acc-{i}")
        assert len(eng._analyses) == 2


# ---------------------------------------------------------------------------
# analyze_access_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_access(
            access_name="acc-001",
            access_type=AccessType.IMPOSSIBLE_TRAVEL,
            anomaly_score=90.0,
        )
        eng.record_access(
            access_name="acc-002",
            access_type=AccessType.IMPOSSIBLE_TRAVEL,
            anomaly_score=70.0,
        )
        result = eng.analyze_access_distribution()
        assert "impossible_travel" in result
        assert result["impossible_travel"]["count"] == 2
        assert result["impossible_travel"]["avg_anomaly_score"] == 80.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_access_distribution() == {}


# ---------------------------------------------------------------------------
# identify_high_anomaly_accesses
# ---------------------------------------------------------------------------


class TestIdentifyHighAnomalyAccesses:
    def test_detects_above_threshold(self):
        eng = _engine(anomaly_score_threshold=80.0)
        eng.record_access(access_name="acc-001", anomaly_score=90.0)
        eng.record_access(access_name="acc-002", anomaly_score=60.0)
        results = eng.identify_high_anomaly_accesses()
        assert len(results) == 1
        assert results[0]["access_name"] == "acc-001"

    def test_sorted_descending(self):
        eng = _engine(anomaly_score_threshold=50.0)
        eng.record_access(access_name="acc-001", anomaly_score=80.0)
        eng.record_access(access_name="acc-002", anomaly_score=95.0)
        results = eng.identify_high_anomaly_accesses()
        assert len(results) == 2
        assert results[0]["anomaly_score"] == 95.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_high_anomaly_accesses() == []


# ---------------------------------------------------------------------------
# rank_by_anomaly
# ---------------------------------------------------------------------------


class TestRankByAnomaly:
    def test_sorted_descending(self):
        eng = _engine()
        eng.record_access(access_name="acc-001", service="auth-svc", anomaly_score=50.0)
        eng.record_access(access_name="acc-002", service="api-gw", anomaly_score=90.0)
        results = eng.rank_by_anomaly()
        assert len(results) == 2
        assert results[0]["service"] == "api-gw"
        assert results[0]["avg_anomaly_score"] == 90.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_anomaly() == []


# ---------------------------------------------------------------------------
# detect_access_trends
# ---------------------------------------------------------------------------


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(access_name="acc-001", analysis_score=50.0)
        result = eng.detect_access_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(access_name="acc-001", analysis_score=20.0)
        eng.add_analysis(access_name="acc-002", analysis_score=20.0)
        eng.add_analysis(access_name="acc-003", analysis_score=80.0)
        eng.add_analysis(access_name="acc-004", analysis_score=80.0)
        result = eng.detect_access_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_access_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(anomaly_score_threshold=80.0)
        eng.record_access(
            access_name="acc-001",
            access_type=AccessType.UNUSUAL_HOURS,
            risk_level=RiskLevel.HIGH,
            detection_method=DetectionMethod.ML_BASED,
            anomaly_score=95.0,
        )
        report = eng.generate_report()
        assert isinstance(report, AccessReport)
        assert report.total_records == 1
        assert report.high_anomaly_count == 1
        assert len(report.top_high_anomaly) == 1
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
        eng.record_access(access_name="acc-001")
        eng.add_analysis(access_name="acc-001")
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
        eng.record_access(
            access_name="acc-001",
            access_type=AccessType.IMPOSSIBLE_TRAVEL,
            service="auth-svc",
            team="security",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "impossible_travel" in stats["type_distribution"]
