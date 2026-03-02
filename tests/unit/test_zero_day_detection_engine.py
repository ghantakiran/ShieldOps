"""Tests for shieldops.security.zero_day_detection_engine — ZeroDayDetectionEngine."""

from __future__ import annotations

from shieldops.security.zero_day_detection_engine import (
    DetectionType,
    ResponseAction,
    ThreatConfidence,
    ZeroDayAnalysis,
    ZeroDayDetectionEngine,
    ZeroDayRecord,
    ZeroDayReport,
)


def _engine(**kw) -> ZeroDayDetectionEngine:
    return ZeroDayDetectionEngine(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_detectiontype_behavioral(self):
        assert DetectionType.BEHAVIORAL == "behavioral"

    def test_detectiontype_heuristic(self):
        assert DetectionType.HEURISTIC == "heuristic"

    def test_detectiontype_sandbox(self):
        assert DetectionType.SANDBOX == "sandbox"

    def test_detectiontype_memory_analysis(self):
        assert DetectionType.MEMORY_ANALYSIS == "memory_analysis"

    def test_detectiontype_network_anomaly(self):
        assert DetectionType.NETWORK_ANOMALY == "network_anomaly"

    def test_threatconfidence_confirmed(self):
        assert ThreatConfidence.CONFIRMED == "confirmed"

    def test_threatconfidence_high(self):
        assert ThreatConfidence.HIGH == "high"

    def test_threatconfidence_medium(self):
        assert ThreatConfidence.MEDIUM == "medium"

    def test_threatconfidence_low(self):
        assert ThreatConfidence.LOW == "low"

    def test_threatconfidence_unconfirmed(self):
        assert ThreatConfidence.UNCONFIRMED == "unconfirmed"

    def test_responseaction_quarantine(self):
        assert ResponseAction.QUARANTINE == "quarantine"

    def test_responseaction_block(self):
        assert ResponseAction.BLOCK == "block"

    def test_responseaction_alert(self):
        assert ResponseAction.ALERT == "alert"

    def test_responseaction_monitor(self):
        assert ResponseAction.MONITOR == "monitor"

    def test_responseaction_allow(self):
        assert ResponseAction.ALLOW == "allow"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_zerodayrecord_defaults(self):
        r = ZeroDayRecord()
        assert r.id
        assert r.detection_name == ""
        assert r.detection_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_zerodayanalysis_defaults(self):
        c = ZeroDayAnalysis()
        assert c.id
        assert c.detection_name == ""
        assert c.analysis_score == 0.0
        assert c.threshold == 0.0
        assert c.breached == 0.0
        assert c.description == ""
        assert c.created_at > 0

    def test_zerodayreport_defaults(self):
        r = ZeroDayReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.low_confidence_count == 0
        assert r.avg_detection_score == 0
        assert r.by_type == {}
        assert r.by_confidence == {}
        assert r.by_action == {}
        assert r.top_low_confidence == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_detection
# ---------------------------------------------------------------------------


class TestRecordDetection:
    def test_basic(self):
        eng = _engine()
        r = eng.record_detection(
            detection_name="test-item",
            detection_type=DetectionType.HEURISTIC,
            detection_score=92.0,
            service="auth-svc",
            team="security",
        )
        assert r.detection_name == "test-item"
        assert r.detection_score == 92.0
        assert r.service == "auth-svc"
        assert r.team == "security"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_detection(detection_name=f"ITEM-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_detection
# ---------------------------------------------------------------------------


class TestGetDetection:
    def test_found(self):
        eng = _engine()
        r = eng.record_detection(detection_name="test-item")
        result = eng.get_detection(r.id)
        assert result is not None
        assert result.detection_name == "test-item"

    def test_not_found(self):
        eng = _engine()
        assert eng.get_detection("nonexistent") is None


# ---------------------------------------------------------------------------
# list_detections
# ---------------------------------------------------------------------------


class TestListDetections:
    def test_list_all(self):
        eng = _engine()
        eng.record_detection(detection_name="ITEM-001")
        eng.record_detection(detection_name="ITEM-002")
        assert len(eng.list_detections()) == 2

    def test_filter_by_detection_type(self):
        eng = _engine()
        eng.record_detection(detection_name="ITEM-001", detection_type=DetectionType.BEHAVIORAL)
        eng.record_detection(detection_name="ITEM-002", detection_type=DetectionType.HEURISTIC)
        results = eng.list_detections(detection_type=DetectionType.BEHAVIORAL)
        assert len(results) == 1

    def test_filter_by_threat_confidence(self):
        eng = _engine()
        eng.record_detection(
            detection_name="ITEM-001", threat_confidence=ThreatConfidence.CONFIRMED
        )
        eng.record_detection(detection_name="ITEM-002", threat_confidence=ThreatConfidence.HIGH)
        results = eng.list_detections(threat_confidence=ThreatConfidence.CONFIRMED)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_detection(detection_name="ITEM-001", team="security")
        eng.record_detection(detection_name="ITEM-002", team="platform")
        results = eng.list_detections(team="security")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_detection(detection_name=f"ITEM-{i}")
        assert len(eng.list_detections(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            detection_name="test-item",
            analysis_score=88.5,
            threshold=80.0,
            breached=True,
            description="test description",
        )
        assert a.detection_name == "test-item"
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(detection_name=f"ITEM-{i}")
        assert len(eng._analyses) == 2


# ---------------------------------------------------------------------------
# analyze_detection_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_detection(
            detection_name="ITEM-001", detection_type=DetectionType.BEHAVIORAL, detection_score=90.0
        )
        eng.record_detection(
            detection_name="ITEM-002", detection_type=DetectionType.BEHAVIORAL, detection_score=70.0
        )
        result = eng.analyze_detection_distribution()
        assert "behavioral" in result
        assert result["behavioral"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_detection_distribution() == {}


# ---------------------------------------------------------------------------
# identify_low_confidence_detections
# ---------------------------------------------------------------------------


class TestIdentifyProblems:
    def test_detects_threshold(self):
        eng = _engine(detection_confidence_threshold=60.0)
        eng.record_detection(detection_name="ITEM-001", detection_score=30.0)
        eng.record_detection(detection_name="ITEM-002", detection_score=90.0)
        results = eng.identify_low_confidence_detections()
        assert len(results) == 1
        assert results[0]["detection_name"] == "ITEM-001"

    def test_sorted_ascending(self):
        eng = _engine(detection_confidence_threshold=60.0)
        eng.record_detection(detection_name="ITEM-001", detection_score=50.0)
        eng.record_detection(detection_name="ITEM-002", detection_score=30.0)
        results = eng.identify_low_confidence_detections()
        assert len(results) == 2
        assert results[0]["detection_score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_low_confidence_detections() == []


# ---------------------------------------------------------------------------
# rank_by_detection_score
# ---------------------------------------------------------------------------


class TestRankByScore:
    def test_sorted(self):
        eng = _engine()
        eng.record_detection(detection_name="ITEM-001", service="auth-svc", detection_score=90.0)
        eng.record_detection(detection_name="ITEM-002", service="api-gw", detection_score=50.0)
        results = eng.rank_by_detection_score()
        assert len(results) == 2
        assert results[0]["service"] == "api-gw"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_detection_score() == []


# ---------------------------------------------------------------------------
# detect_detection_trends
# ---------------------------------------------------------------------------


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(detection_name="ITEM-001", analysis_score=50.0)
        result = eng.detect_detection_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(detection_name="ITEM-001", analysis_score=20.0)
        eng.add_analysis(detection_name="ITEM-002", analysis_score=20.0)
        eng.add_analysis(detection_name="ITEM-003", analysis_score=80.0)
        eng.add_analysis(detection_name="ITEM-004", analysis_score=80.0)
        result = eng.detect_detection_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_detection_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(detection_confidence_threshold=60.0)
        eng.record_detection(detection_name="test-item", detection_score=30.0)
        report = eng.generate_report()
        assert isinstance(report, ZeroDayReport)
        assert report.total_records == 1
        assert report.low_confidence_count == 1
        assert len(report.top_low_confidence) == 1
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
        eng.record_detection(detection_name="ITEM-001")
        eng.add_analysis(detection_name="ITEM-001")
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

    def test_populated(self):
        eng = _engine()
        eng.record_detection(
            detection_name="ITEM-001",
            detection_type=DetectionType.BEHAVIORAL,
            service="auth-svc",
            team="security",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
