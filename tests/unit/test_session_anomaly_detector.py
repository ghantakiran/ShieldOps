"""Tests for shieldops.analytics.session_anomaly_detector — SessionAnomalyDetector."""

from __future__ import annotations

from shieldops.analytics.session_anomaly_detector import (
    AnomalyType,
    DetectionMethod,
    SessionAnalysis,
    SessionAnomalyDetector,
    SessionAnomalyReport,
    SessionRecord,
    SessionType,
)


def _engine(**kw) -> SessionAnomalyDetector:
    return SessionAnomalyDetector(**kw)


class TestEnums:
    def test_session_interactive(self):
        assert SessionType.INTERACTIVE == "interactive"

    def test_session_api(self):
        assert SessionType.API == "api"

    def test_session_service(self):
        assert SessionType.SERVICE == "service"

    def test_session_vpn(self):
        assert SessionType.VPN == "vpn"

    def test_session_remote_desktop(self):
        assert SessionType.REMOTE_DESKTOP == "remote_desktop"

    def test_anomaly_impossible_travel(self):
        assert AnomalyType.IMPOSSIBLE_TRAVEL == "impossible_travel"

    def test_anomaly_unusual_time(self):
        assert AnomalyType.UNUSUAL_TIME == "unusual_time"

    def test_anomaly_excessive_duration(self):
        assert AnomalyType.EXCESSIVE_DURATION == "excessive_duration"

    def test_anomaly_suspicious_activity(self):
        assert AnomalyType.SUSPICIOUS_ACTIVITY == "suspicious_activity"

    def test_anomaly_concurrent_session(self):
        assert AnomalyType.CONCURRENT_SESSION == "concurrent_session"

    def test_method_statistical(self):
        assert DetectionMethod.STATISTICAL == "statistical"

    def test_method_ml_based(self):
        assert DetectionMethod.ML_BASED == "ml_based"

    def test_method_rule_based(self):
        assert DetectionMethod.RULE_BASED == "rule_based"

    def test_method_behavioral(self):
        assert DetectionMethod.BEHAVIORAL == "behavioral"

    def test_method_hybrid(self):
        assert DetectionMethod.HYBRID == "hybrid"


class TestModels:
    def test_record_defaults(self):
        r = SessionRecord()
        assert r.id
        assert r.session_name == ""
        assert r.session_type == SessionType.INTERACTIVE
        assert r.anomaly_type == AnomalyType.IMPOSSIBLE_TRAVEL
        assert r.detection_method == DetectionMethod.STATISTICAL
        assert r.anomaly_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_analysis_defaults(self):
        a = SessionAnalysis()
        assert a.id
        assert a.session_name == ""
        assert a.session_type == SessionType.INTERACTIVE
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = SessionAnomalyReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_anomaly_score == 0.0
        assert r.by_session_type == {}
        assert r.by_anomaly_type == {}
        assert r.by_detection_method == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_session(
            session_name="sess-001",
            session_type=SessionType.API,
            anomaly_type=AnomalyType.UNUSUAL_TIME,
            detection_method=DetectionMethod.ML_BASED,
            anomaly_score=85.0,
            service="gateway-svc",
            team="platform",
        )
        assert r.session_name == "sess-001"
        assert r.session_type == SessionType.API
        assert r.anomaly_score == 85.0
        assert r.service == "gateway-svc"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_session(session_name=f"sess-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_session(session_name="test")
        assert eng.get_record(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_record("nonexistent") is None


class TestList:
    def test_list_all(self):
        eng = _engine()
        eng.record_session(session_name="a")
        eng.record_session(session_name="b")
        assert len(eng.list_records()) == 2

    def test_filter_by_session_type(self):
        eng = _engine()
        eng.record_session(session_name="a", session_type=SessionType.INTERACTIVE)
        eng.record_session(session_name="b", session_type=SessionType.VPN)
        assert len(eng.list_records(session_type=SessionType.INTERACTIVE)) == 1

    def test_filter_by_anomaly_type(self):
        eng = _engine()
        eng.record_session(session_name="a", anomaly_type=AnomalyType.IMPOSSIBLE_TRAVEL)
        eng.record_session(session_name="b", anomaly_type=AnomalyType.UNUSUAL_TIME)
        assert len(eng.list_records(anomaly_type=AnomalyType.IMPOSSIBLE_TRAVEL)) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_session(session_name="a", team="sec")
        eng.record_session(session_name="b", team="ops")
        assert len(eng.list_records(team="sec")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_session(session_name=f"s-{i}")
        assert len(eng.list_records(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            session_name="test", analysis_score=88.5, breached=True, description="anomaly"
        )
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(session_name=f"t-{i}")
        assert len(eng._analyses) == 2


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_session(
            session_name="a", session_type=SessionType.INTERACTIVE, anomaly_score=90.0
        )
        eng.record_session(
            session_name="b", session_type=SessionType.INTERACTIVE, anomaly_score=70.0
        )
        result = eng.analyze_distribution()
        assert "interactive" in result
        assert result["interactive"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(threshold=80.0)
        eng.record_session(session_name="a", anomaly_score=60.0)
        eng.record_session(session_name="b", anomaly_score=90.0)
        assert len(eng.identify_gaps()) == 1

    def test_sorted_ascending(self):
        eng = _engine(threshold=80.0)
        eng.record_session(session_name="a", anomaly_score=50.0)
        eng.record_session(session_name="b", anomaly_score=30.0)
        results = eng.identify_gaps()
        assert results[0]["anomaly_score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_gaps() == []


class TestRankByScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_session(session_name="a", service="auth", anomaly_score=90.0)
        eng.record_session(session_name="b", service="api", anomaly_score=50.0)
        results = eng.rank_by_score()
        assert results[0]["service"] == "api"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_score() == []


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(session_name="t", analysis_score=50.0)
        assert eng.detect_trends()["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(session_name="a", analysis_score=20.0)
        eng.add_analysis(session_name="b", analysis_score=20.0)
        eng.add_analysis(session_name="c", analysis_score=80.0)
        eng.add_analysis(session_name="d", analysis_score=80.0)
        assert eng.detect_trends()["trend"] == "improving"

    def test_insufficient_data(self):
        eng = _engine()
        assert eng.detect_trends()["trend"] == "insufficient_data"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(threshold=80.0)
        eng.record_session(session_name="test", anomaly_score=50.0)
        report = eng.generate_report()
        assert report.total_records == 1
        assert report.gap_count == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_session(session_name="test")
        eng.add_analysis(session_name="test")
        assert eng.clear_data() == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0

    def test_populated(self):
        eng = _engine()
        eng.record_session(session_name="test", service="auth", team="sec")
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
