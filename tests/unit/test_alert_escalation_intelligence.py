"""Tests for shieldops.incidents.alert_escalation_intelligence — AlertEscalationIntelligence."""

from __future__ import annotations

from shieldops.incidents.alert_escalation_intelligence import (
    AlertEscalationIntelligence,
    EscalationAnalysis,
    EscalationOutcome,
    EscalationPath,
    EscalationRecord,
    EscalationReport,
    EscalationSpeed,
)


def _engine(**kw) -> AlertEscalationIntelligence:
    return AlertEscalationIntelligence(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_path_direct(self):
        assert EscalationPath.DIRECT == "direct"

    def test_path_tiered(self):
        assert EscalationPath.TIERED == "tiered"

    def test_path_automated(self):
        assert EscalationPath.AUTOMATED == "automated"

    def test_path_hybrid(self):
        assert EscalationPath.HYBRID == "hybrid"

    def test_path_skip_level(self):
        assert EscalationPath.SKIP_LEVEL == "skip_level"

    def test_outcome_resolved(self):
        assert EscalationOutcome.RESOLVED == "resolved"

    def test_outcome_reassigned(self):
        assert EscalationOutcome.REASSIGNED == "reassigned"

    def test_outcome_timed_out(self):
        assert EscalationOutcome.TIMED_OUT == "timed_out"

    def test_outcome_escalated_further(self):
        assert EscalationOutcome.ESCALATED_FURTHER == "escalated_further"

    def test_outcome_closed_no_action(self):
        assert EscalationOutcome.CLOSED_NO_ACTION == "closed_no_action"

    def test_speed_immediate(self):
        assert EscalationSpeed.IMMEDIATE == "immediate"

    def test_speed_fast(self):
        assert EscalationSpeed.FAST == "fast"

    def test_speed_normal(self):
        assert EscalationSpeed.NORMAL == "normal"

    def test_speed_slow(self):
        assert EscalationSpeed.SLOW == "slow"

    def test_speed_delayed(self):
        assert EscalationSpeed.DELAYED == "delayed"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_escalation_record_defaults(self):
        r = EscalationRecord()
        assert r.id
        assert r.escalation_name == ""
        assert r.escalation_path == EscalationPath.DIRECT
        assert r.escalation_outcome == EscalationOutcome.RESOLVED
        assert r.escalation_speed == EscalationSpeed.IMMEDIATE
        assert r.effectiveness_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_escalation_analysis_defaults(self):
        c = EscalationAnalysis()
        assert c.id
        assert c.escalation_name == ""
        assert c.escalation_path == EscalationPath.DIRECT
        assert c.analysis_score == 0.0
        assert c.threshold == 0.0
        assert c.breached is False
        assert c.description == ""
        assert c.created_at > 0

    def test_escalation_report_defaults(self):
        r = EscalationReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.low_effectiveness_count == 0
        assert r.avg_effectiveness_score == 0.0
        assert r.by_path == {}
        assert r.by_outcome == {}
        assert r.by_speed == {}
        assert r.top_low_effectiveness == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_escalation
# ---------------------------------------------------------------------------


class TestRecordEscalation:
    def test_basic(self):
        eng = _engine()
        r = eng.record_escalation(
            escalation_name="critical-db-outage",
            escalation_path=EscalationPath.TIERED,
            escalation_outcome=EscalationOutcome.RESOLVED,
            escalation_speed=EscalationSpeed.FAST,
            effectiveness_score=92.0,
            service="auth-svc",
            team="security",
        )
        assert r.escalation_name == "critical-db-outage"
        assert r.escalation_path == EscalationPath.TIERED
        assert r.escalation_outcome == EscalationOutcome.RESOLVED
        assert r.escalation_speed == EscalationSpeed.FAST
        assert r.effectiveness_score == 92.0
        assert r.service == "auth-svc"
        assert r.team == "security"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_escalation(escalation_name=f"ESC-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_escalation
# ---------------------------------------------------------------------------


class TestGetEscalation:
    def test_found(self):
        eng = _engine()
        r = eng.record_escalation(
            escalation_name="critical-db-outage",
            escalation_outcome=EscalationOutcome.CLOSED_NO_ACTION,
        )
        result = eng.get_escalation(r.id)
        assert result is not None
        assert result.escalation_outcome == EscalationOutcome.CLOSED_NO_ACTION

    def test_not_found(self):
        eng = _engine()
        assert eng.get_escalation("nonexistent") is None


# ---------------------------------------------------------------------------
# list_escalations
# ---------------------------------------------------------------------------


class TestListEscalations:
    def test_list_all(self):
        eng = _engine()
        eng.record_escalation(escalation_name="ESC-001")
        eng.record_escalation(escalation_name="ESC-002")
        assert len(eng.list_escalations()) == 2

    def test_filter_by_path(self):
        eng = _engine()
        eng.record_escalation(
            escalation_name="ESC-001",
            escalation_path=EscalationPath.DIRECT,
        )
        eng.record_escalation(
            escalation_name="ESC-002",
            escalation_path=EscalationPath.SKIP_LEVEL,
        )
        results = eng.list_escalations(escalation_path=EscalationPath.DIRECT)
        assert len(results) == 1

    def test_filter_by_outcome(self):
        eng = _engine()
        eng.record_escalation(
            escalation_name="ESC-001",
            escalation_outcome=EscalationOutcome.RESOLVED,
        )
        eng.record_escalation(
            escalation_name="ESC-002",
            escalation_outcome=EscalationOutcome.TIMED_OUT,
        )
        results = eng.list_escalations(
            escalation_outcome=EscalationOutcome.RESOLVED,
        )
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_escalation(escalation_name="ESC-001", team="security")
        eng.record_escalation(escalation_name="ESC-002", team="platform")
        results = eng.list_escalations(team="security")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_escalation(escalation_name=f"ESC-{i}")
        assert len(eng.list_escalations(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        c = eng.add_analysis(
            escalation_name="critical-db-outage",
            escalation_path=EscalationPath.AUTOMATED,
            analysis_score=88.5,
        )
        assert c.escalation_name == "critical-db-outage"
        assert c.escalation_path == EscalationPath.AUTOMATED
        assert c.analysis_score == 88.5

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(escalation_name=f"ESC-{i}")
        assert len(eng._analyses) == 2


# ---------------------------------------------------------------------------
# analyze_escalation_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_escalation(
            escalation_name="ESC-001",
            escalation_path=EscalationPath.DIRECT,
            effectiveness_score=90.0,
        )
        eng.record_escalation(
            escalation_name="ESC-002",
            escalation_path=EscalationPath.DIRECT,
            effectiveness_score=70.0,
        )
        result = eng.analyze_escalation_distribution()
        assert "direct" in result
        assert result["direct"]["count"] == 2
        assert result["direct"]["avg_effectiveness_score"] == 80.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_escalation_distribution() == {}


# ---------------------------------------------------------------------------
# identify_low_effectiveness_escalations
# ---------------------------------------------------------------------------


class TestIdentifyLowEffectivenessEscalations:
    def test_detects_below_threshold(self):
        eng = _engine(escalation_effectiveness_threshold=80.0)
        eng.record_escalation(escalation_name="ESC-001", effectiveness_score=60.0)
        eng.record_escalation(escalation_name="ESC-002", effectiveness_score=90.0)
        results = eng.identify_low_effectiveness_escalations()
        assert len(results) == 1
        assert results[0]["escalation_name"] == "ESC-001"

    def test_sorted_ascending(self):
        eng = _engine(escalation_effectiveness_threshold=80.0)
        eng.record_escalation(escalation_name="ESC-001", effectiveness_score=50.0)
        eng.record_escalation(escalation_name="ESC-002", effectiveness_score=30.0)
        results = eng.identify_low_effectiveness_escalations()
        assert len(results) == 2
        assert results[0]["effectiveness_score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_low_effectiveness_escalations() == []


# ---------------------------------------------------------------------------
# rank_by_effectiveness
# ---------------------------------------------------------------------------


class TestRankByEffectiveness:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_escalation(
            escalation_name="ESC-001", service="auth-svc", effectiveness_score=90.0
        )
        eng.record_escalation(escalation_name="ESC-002", service="api-gw", effectiveness_score=50.0)
        results = eng.rank_by_effectiveness()
        assert len(results) == 2
        assert results[0]["service"] == "api-gw"
        assert results[0]["avg_effectiveness_score"] == 50.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_effectiveness() == []


# ---------------------------------------------------------------------------
# detect_escalation_trends
# ---------------------------------------------------------------------------


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(escalation_name="ESC-001", analysis_score=50.0)
        result = eng.detect_escalation_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(escalation_name="ESC-001", analysis_score=20.0)
        eng.add_analysis(escalation_name="ESC-002", analysis_score=20.0)
        eng.add_analysis(escalation_name="ESC-003", analysis_score=80.0)
        eng.add_analysis(escalation_name="ESC-004", analysis_score=80.0)
        result = eng.detect_escalation_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_escalation_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(escalation_effectiveness_threshold=80.0)
        eng.record_escalation(
            escalation_name="critical-db-outage",
            escalation_path=EscalationPath.TIERED,
            escalation_outcome=EscalationOutcome.REASSIGNED,
            escalation_speed=EscalationSpeed.SLOW,
            effectiveness_score=50.0,
        )
        report = eng.generate_report()
        assert isinstance(report, EscalationReport)
        assert report.total_records == 1
        assert report.low_effectiveness_count == 1
        assert len(report.top_low_effectiveness) == 1
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
        eng.record_escalation(escalation_name="ESC-001")
        eng.add_analysis(escalation_name="ESC-001")
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
        assert stats["path_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_escalation(
            escalation_name="ESC-001",
            escalation_path=EscalationPath.DIRECT,
            service="auth-svc",
            team="security",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "direct" in stats["path_distribution"]
