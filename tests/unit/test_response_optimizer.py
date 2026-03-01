"""Tests for shieldops.incidents.response_optimizer — IncidentResponseOptimizer."""

from __future__ import annotations

from shieldops.incidents.response_optimizer import (
    EscalationLevel,
    IncidentResponseOptimizer,
    ResponseEfficiency,
    ResponseOptimizerReport,
    ResponsePattern,
    ResponsePhase,
    ResponseRecord,
)


def _engine(**kw) -> IncidentResponseOptimizer:
    return IncidentResponseOptimizer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_phase_detection(self):
        assert ResponsePhase.DETECTION == "detection"

    def test_phase_triage(self):
        assert ResponsePhase.TRIAGE == "triage"

    def test_phase_investigation(self):
        assert ResponsePhase.INVESTIGATION == "investigation"

    def test_phase_mitigation(self):
        assert ResponsePhase.MITIGATION == "mitigation"

    def test_phase_resolution(self):
        assert ResponsePhase.RESOLUTION == "resolution"

    def test_efficiency_excellent(self):
        assert ResponseEfficiency.EXCELLENT == "excellent"

    def test_efficiency_good(self):
        assert ResponseEfficiency.GOOD == "good"

    def test_efficiency_adequate(self):
        assert ResponseEfficiency.ADEQUATE == "adequate"

    def test_efficiency_slow(self):
        assert ResponseEfficiency.SLOW == "slow"

    def test_efficiency_critical(self):
        assert ResponseEfficiency.CRITICAL == "critical"

    def test_escalation_l1(self):
        assert EscalationLevel.L1 == "l1"

    def test_escalation_l2(self):
        assert EscalationLevel.L2 == "l2"

    def test_escalation_l3(self):
        assert EscalationLevel.L3 == "l3"

    def test_escalation_management(self):
        assert EscalationLevel.MANAGEMENT == "management"

    def test_escalation_executive(self):
        assert EscalationLevel.EXECUTIVE == "executive"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_response_record_defaults(self):
        r = ResponseRecord()
        assert r.id
        assert r.incident_id == ""
        assert r.response_phase == ResponsePhase.DETECTION
        assert r.response_efficiency == ResponseEfficiency.ADEQUATE
        assert r.escalation_level == EscalationLevel.L1
        assert r.response_time_minutes == 0.0
        assert r.team == ""
        assert r.created_at > 0

    def test_response_pattern_defaults(self):
        p = ResponsePattern()
        assert p.id
        assert p.phase_pattern == ""
        assert p.response_phase == ResponsePhase.DETECTION
        assert p.efficiency_threshold == 0.0
        assert p.avg_time_minutes == 0.0
        assert p.description == ""
        assert p.created_at > 0

    def test_response_optimizer_report_defaults(self):
        r = ResponseOptimizerReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_patterns == 0
        assert r.slow_responses == 0
        assert r.avg_response_time == 0.0
        assert r.by_phase == {}
        assert r.by_efficiency == {}
        assert r.by_escalation == {}
        assert r.bottlenecks == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_response
# ---------------------------------------------------------------------------


class TestRecordResponse:
    def test_basic(self):
        eng = _engine()
        r = eng.record_response(
            incident_id="INC-001",
            response_phase=ResponsePhase.TRIAGE,
            response_efficiency=ResponseEfficiency.GOOD,
            escalation_level=EscalationLevel.L2,
            response_time_minutes=12.5,
            team="sre",
        )
        assert r.incident_id == "INC-001"
        assert r.response_phase == ResponsePhase.TRIAGE
        assert r.response_efficiency == ResponseEfficiency.GOOD
        assert r.escalation_level == EscalationLevel.L2
        assert r.response_time_minutes == 12.5
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_response(incident_id=f"INC-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_response
# ---------------------------------------------------------------------------


class TestGetResponse:
    def test_found(self):
        eng = _engine()
        r = eng.record_response(
            incident_id="INC-001",
            response_efficiency=ResponseEfficiency.EXCELLENT,
        )
        result = eng.get_response(r.id)
        assert result is not None
        assert result.response_efficiency == ResponseEfficiency.EXCELLENT

    def test_not_found(self):
        eng = _engine()
        assert eng.get_response("nonexistent") is None


# ---------------------------------------------------------------------------
# list_responses
# ---------------------------------------------------------------------------


class TestListResponses:
    def test_list_all(self):
        eng = _engine()
        eng.record_response(incident_id="INC-001")
        eng.record_response(incident_id="INC-002")
        assert len(eng.list_responses()) == 2

    def test_filter_by_phase(self):
        eng = _engine()
        eng.record_response(
            incident_id="INC-001",
            response_phase=ResponsePhase.TRIAGE,
        )
        eng.record_response(
            incident_id="INC-002",
            response_phase=ResponsePhase.RESOLUTION,
        )
        results = eng.list_responses(phase=ResponsePhase.TRIAGE)
        assert len(results) == 1

    def test_filter_by_efficiency(self):
        eng = _engine()
        eng.record_response(
            incident_id="INC-001",
            response_efficiency=ResponseEfficiency.EXCELLENT,
        )
        eng.record_response(
            incident_id="INC-002",
            response_efficiency=ResponseEfficiency.SLOW,
        )
        results = eng.list_responses(efficiency=ResponseEfficiency.EXCELLENT)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_response(incident_id="INC-001", team="sre")
        eng.record_response(incident_id="INC-002", team="platform")
        results = eng.list_responses(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_response(incident_id=f"INC-{i}")
        assert len(eng.list_responses(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_pattern
# ---------------------------------------------------------------------------


class TestAddPattern:
    def test_basic(self):
        eng = _engine()
        p = eng.add_pattern(
            phase_pattern="slow-triage",
            response_phase=ResponsePhase.TRIAGE,
            efficiency_threshold=0.8,
            avg_time_minutes=15.0,
            description="Slow triage pattern",
        )
        assert p.phase_pattern == "slow-triage"
        assert p.response_phase == ResponsePhase.TRIAGE
        assert p.efficiency_threshold == 0.8
        assert p.avg_time_minutes == 15.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_pattern(phase_pattern=f"pat-{i}")
        assert len(eng._patterns) == 2


# ---------------------------------------------------------------------------
# analyze_response_efficiency
# ---------------------------------------------------------------------------


class TestAnalyzeResponseEfficiency:
    def test_with_data(self):
        eng = _engine()
        eng.record_response(
            incident_id="INC-001",
            response_phase=ResponsePhase.TRIAGE,
            response_time_minutes=10.0,
        )
        eng.record_response(
            incident_id="INC-002",
            response_phase=ResponsePhase.TRIAGE,
            response_time_minutes=20.0,
        )
        result = eng.analyze_response_efficiency()
        assert "triage" in result
        assert result["triage"]["count"] == 2
        assert result["triage"]["avg_response_time"] == 15.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_response_efficiency() == {}


# ---------------------------------------------------------------------------
# identify_bottlenecks
# ---------------------------------------------------------------------------


class TestIdentifyBottlenecks:
    def test_detects_slow(self):
        eng = _engine()
        eng.record_response(
            incident_id="INC-001",
            response_efficiency=ResponseEfficiency.SLOW,
            response_time_minutes=45.0,
        )
        eng.record_response(
            incident_id="INC-002",
            response_efficiency=ResponseEfficiency.EXCELLENT,
        )
        results = eng.identify_bottlenecks()
        assert len(results) == 1
        assert results[0]["incident_id"] == "INC-001"

    def test_detects_critical(self):
        eng = _engine()
        eng.record_response(
            incident_id="INC-001",
            response_efficiency=ResponseEfficiency.CRITICAL,
        )
        results = eng.identify_bottlenecks()
        assert len(results) == 1

    def test_empty(self):
        eng = _engine()
        assert eng.identify_bottlenecks() == []


# ---------------------------------------------------------------------------
# rank_by_response_time
# ---------------------------------------------------------------------------


class TestRankByResponseTime:
    def test_ranked_descending(self):
        eng = _engine()
        eng.record_response(incident_id="INC-001", team="sre", response_time_minutes=30.0)
        eng.record_response(incident_id="INC-002", team="sre", response_time_minutes=20.0)
        eng.record_response(incident_id="INC-003", team="platform", response_time_minutes=10.0)
        results = eng.rank_by_response_time()
        assert len(results) == 2
        assert results[0]["team"] == "sre"
        assert results[0]["avg_response_time"] == 25.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_response_time() == []


# ---------------------------------------------------------------------------
# detect_response_trends
# ---------------------------------------------------------------------------


class TestDetectResponseTrends:
    def test_stable(self):
        eng = _engine()
        for t in [10.0, 10.0, 10.0, 10.0]:
            eng.add_pattern(phase_pattern="p", avg_time_minutes=t)
        result = eng.detect_response_trends()
        assert result["trend"] == "stable"

    def test_increasing(self):
        eng = _engine()
        for t in [5.0, 5.0, 20.0, 20.0]:
            eng.add_pattern(phase_pattern="p", avg_time_minutes=t)
        result = eng.detect_response_trends()
        assert result["trend"] == "increasing"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_response_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_response(
            incident_id="INC-001",
            response_phase=ResponsePhase.TRIAGE,
            response_efficiency=ResponseEfficiency.SLOW,
            response_time_minutes=45.0,
            team="sre",
        )
        report = eng.generate_report()
        assert isinstance(report, ResponseOptimizerReport)
        assert report.total_records == 1
        assert report.slow_responses == 1
        assert report.avg_response_time == 45.0
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "acceptable" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_response(incident_id="INC-001")
        eng.add_pattern(phase_pattern="p1")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._patterns) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_patterns"] == 0
        assert stats["phase_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_response(
            incident_id="INC-001",
            response_phase=ResponsePhase.TRIAGE,
            team="sre",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_incidents"] == 1
        assert "triage" in stats["phase_distribution"]
