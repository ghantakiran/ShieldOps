"""Tests for shieldops.incidents.handoff_tracker — IncidentHandoffTracker."""

from __future__ import annotations

from shieldops.incidents.handoff_tracker import (
    HandoffPattern,
    HandoffQuality,
    HandoffRecord,
    HandoffReport,
    HandoffType,
    IncidentHandoffTracker,
    InformationCompleteness,
)


def _engine(**kw) -> IncidentHandoffTracker:
    return IncidentHandoffTracker(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    # HandoffType (5)
    def test_type_shift_change(self):
        assert HandoffType.SHIFT_CHANGE == "shift_change"

    def test_type_escalation(self):
        assert HandoffType.ESCALATION == "escalation"

    def test_type_cross_team(self):
        assert HandoffType.CROSS_TEAM == "cross_team"

    def test_type_specialization(self):
        assert HandoffType.SPECIALIZATION == "specialization"

    def test_type_management(self):
        assert HandoffType.MANAGEMENT == "management"

    # HandoffQuality (5)
    def test_quality_excellent(self):
        assert HandoffQuality.EXCELLENT == "excellent"

    def test_quality_good(self):
        assert HandoffQuality.GOOD == "good"

    def test_quality_adequate(self):
        assert HandoffQuality.ADEQUATE == "adequate"

    def test_quality_poor(self):
        assert HandoffQuality.POOR == "poor"

    def test_quality_failed(self):
        assert HandoffQuality.FAILED == "failed"

    # InformationCompleteness (5)
    def test_completeness_full_context(self):
        assert InformationCompleteness.FULL_CONTEXT == "full_context"

    def test_completeness_mostly_complete(self):
        assert InformationCompleteness.MOSTLY_COMPLETE == "mostly_complete"

    def test_completeness_partial(self):
        assert InformationCompleteness.PARTIAL == "partial"

    def test_completeness_minimal(self):
        assert InformationCompleteness.MINIMAL == "minimal"

    def test_completeness_no_context(self):
        assert InformationCompleteness.NO_CONTEXT == "no_context"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_handoff_record_defaults(self):
        r = HandoffRecord()
        assert r.id
        assert r.incident_id == ""
        assert r.from_responder == ""
        assert r.to_responder == ""
        assert r.handoff_type == HandoffType.SHIFT_CHANGE
        assert r.quality == HandoffQuality.ADEQUATE
        assert r.completeness == InformationCompleteness.PARTIAL
        assert r.delay_minutes == 0.0
        assert r.notes_provided is False
        assert r.runbook_attached is False
        assert r.quality_score == 0.5
        assert r.created_at > 0

    def test_handoff_pattern_defaults(self):
        p = HandoffPattern()
        assert p.id
        assert p.pattern_name == ""
        assert p.handoff_type == HandoffType.SHIFT_CHANGE
        assert p.frequency == 0
        assert p.avg_quality_score == 0.0
        assert p.common_issues == []
        assert p.created_at > 0

    def test_handoff_report_defaults(self):
        r = HandoffReport()
        assert r.total_handoffs == 0
        assert r.avg_quality_score == 0.0
        assert r.by_type == {}
        assert r.by_quality == {}
        assert r.problem_pairs == []
        assert r.avg_delay_minutes == 0.0
        assert r.recommendations == []
        assert r.generated_at > 0


# ---------------------------------------------------------------------------
# record_handoff
# ---------------------------------------------------------------------------


class TestRecordHandoff:
    def test_basic(self):
        eng = _engine()
        rec = eng.record_handoff(
            incident_id="INC-1",
            from_responder="alice",
            to_responder="bob",
        )
        assert rec.incident_id == "INC-1"
        assert rec.from_responder == "alice"
        assert rec.to_responder == "bob"
        assert rec.handoff_type == HandoffType.SHIFT_CHANGE

    def test_with_notes_and_runbook_high_quality(self):
        eng = _engine()
        rec = eng.record_handoff(
            incident_id="INC-2",
            from_responder="alice",
            to_responder="bob",
            delay_minutes=2.0,
            notes_provided=True,
            runbook_attached=True,
        )
        # 0.5 + 0.2 (notes) + 0.15 (runbook) + 0.15 (delay<5) = 1.0
        assert rec.quality_score == 1.0
        assert rec.quality == HandoffQuality.EXCELLENT
        assert rec.completeness == InformationCompleteness.FULL_CONTEXT

    def test_no_notes_high_delay_low_quality(self):
        eng = _engine()
        rec = eng.record_handoff(
            incident_id="INC-3",
            from_responder="alice",
            to_responder="bob",
            delay_minutes=60.0,
            notes_provided=False,
            runbook_attached=False,
        )
        # 0.5 - 0.1 (delay>=30) = 0.4
        assert rec.quality_score == 0.4
        assert rec.quality == HandoffQuality.POOR

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_handoff(
                incident_id=f"INC-{i}",
                from_responder="alice",
                to_responder="bob",
            )
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_handoff
# ---------------------------------------------------------------------------


class TestGetHandoff:
    def test_found(self):
        eng = _engine()
        rec = eng.record_handoff("INC-1", "alice", "bob")
        result = eng.get_handoff(rec.id)
        assert result is not None
        assert result.incident_id == "INC-1"

    def test_not_found(self):
        eng = _engine()
        assert eng.get_handoff("nonexistent") is None


# ---------------------------------------------------------------------------
# list_handoffs
# ---------------------------------------------------------------------------


class TestListHandoffs:
    def test_list_all(self):
        eng = _engine()
        eng.record_handoff("INC-1", "alice", "bob")
        eng.record_handoff("INC-2", "bob", "carol")
        assert len(eng.list_handoffs()) == 2

    def test_filter_by_incident(self):
        eng = _engine()
        eng.record_handoff("INC-1", "alice", "bob")
        eng.record_handoff("INC-2", "bob", "carol")
        results = eng.list_handoffs(incident_id="INC-1")
        assert len(results) == 1
        assert results[0].incident_id == "INC-1"

    def test_filter_by_type(self):
        eng = _engine()
        eng.record_handoff("INC-1", "alice", "bob", handoff_type=HandoffType.ESCALATION)
        eng.record_handoff("INC-2", "bob", "carol", handoff_type=HandoffType.SHIFT_CHANGE)
        results = eng.list_handoffs(handoff_type=HandoffType.ESCALATION)
        assert len(results) == 1


# ---------------------------------------------------------------------------
# assess_quality
# ---------------------------------------------------------------------------


class TestAssessQuality:
    def test_existing_record(self):
        eng = _engine()
        rec = eng.record_handoff("INC-1", "alice", "bob", notes_provided=True)
        result = eng.assess_quality(rec.id)
        assert result["record_id"] == rec.id
        assert "quality_score" in result
        assert "quality" in result
        assert "completeness" in result
        assert "meets_threshold" in result

    def test_not_found(self):
        eng = _engine()
        result = eng.assess_quality("bad-id")
        assert result["error"] == "Record not found"


# ---------------------------------------------------------------------------
# detect_patterns
# ---------------------------------------------------------------------------


class TestDetectPatterns:
    def test_with_patterns(self):
        eng = _engine()
        eng.record_handoff("INC-1", "alice", "bob", handoff_type=HandoffType.SHIFT_CHANGE)
        eng.record_handoff("INC-2", "bob", "carol", handoff_type=HandoffType.ESCALATION)
        eng.record_handoff("INC-3", "carol", "dave", handoff_type=HandoffType.SHIFT_CHANGE)
        patterns = eng.detect_patterns()
        assert len(patterns) == 2
        assert all(isinstance(p, HandoffPattern) for p in patterns)

    def test_empty(self):
        eng = _engine()
        patterns = eng.detect_patterns()
        assert patterns == []


# ---------------------------------------------------------------------------
# identify_problem_pairs
# ---------------------------------------------------------------------------


class TestIdentifyProblemPairs:
    def test_has_problem_pairs(self):
        eng = _engine(quality_threshold=0.7)
        # Two low-quality handoffs for same pair (delay>=30, no notes, no runbook => 0.4)
        eng.record_handoff("INC-1", "alice", "bob", delay_minutes=60.0)
        eng.record_handoff("INC-2", "alice", "bob", delay_minutes=60.0)
        pairs = eng.identify_problem_pairs()
        assert len(pairs) == 1
        assert pairs[0]["pair"] == "alice->bob"
        assert pairs[0]["below_threshold"] is True

    def test_no_problem_pairs(self):
        eng = _engine()
        eng.record_handoff(
            "INC-1",
            "alice",
            "bob",
            delay_minutes=2.0,
            notes_provided=True,
            runbook_attached=True,
        )
        eng.record_handoff(
            "INC-2",
            "alice",
            "bob",
            delay_minutes=2.0,
            notes_provided=True,
            runbook_attached=True,
        )
        pairs = eng.identify_problem_pairs()
        assert pairs == []


# ---------------------------------------------------------------------------
# calculate_avg_delay
# ---------------------------------------------------------------------------


class TestCalculateAvgDelay:
    def test_with_data(self):
        eng = _engine()
        eng.record_handoff("INC-1", "alice", "bob", delay_minutes=10.0)
        eng.record_handoff("INC-2", "bob", "carol", delay_minutes=20.0)
        result = eng.calculate_avg_delay()
        assert result["overall_avg_delay_minutes"] == 15.0
        assert result["total_handoffs"] == 2
        assert "by_type" in result

    def test_empty(self):
        eng = _engine()
        result = eng.calculate_avg_delay()
        assert result["overall_avg_delay_minutes"] == 0.0
        assert result["total_handoffs"] == 0


# ---------------------------------------------------------------------------
# rank_by_information_loss
# ---------------------------------------------------------------------------


class TestRankByInformationLoss:
    def test_ranked_by_quality_score(self):
        eng = _engine()
        eng.record_handoff("INC-1", "alice", "bob", delay_minutes=60.0)
        eng.record_handoff(
            "INC-2",
            "bob",
            "carol",
            delay_minutes=2.0,
            notes_provided=True,
            runbook_attached=True,
        )
        ranked = eng.rank_by_information_loss()
        assert len(ranked) == 2
        # Worst quality first
        assert ranked[0]["quality_score"] <= ranked[1]["quality_score"]

    def test_empty(self):
        eng = _engine()
        ranked = eng.rank_by_information_loss()
        assert ranked == []


# ---------------------------------------------------------------------------
# generate_handoff_report
# ---------------------------------------------------------------------------


class TestGenerateHandoffReport:
    def test_basic_report(self):
        eng = _engine()
        eng.record_handoff("INC-1", "alice", "bob", delay_minutes=5.0)
        eng.record_handoff("INC-2", "bob", "carol", delay_minutes=10.0)
        report = eng.generate_handoff_report()
        assert report.total_handoffs == 2
        assert report.avg_quality_score > 0
        assert len(report.by_type) > 0
        assert len(report.by_quality) > 0
        assert len(report.recommendations) > 0
        assert report.generated_at > 0

    def test_empty_report(self):
        eng = _engine()
        report = eng.generate_handoff_report()
        assert report.total_handoffs == 0
        assert report.avg_quality_score == 0.0


# ---------------------------------------------------------------------------
# clear_data
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears_all(self):
        eng = _engine()
        eng.record_handoff("INC-1", "alice", "bob")
        eng.detect_patterns()
        assert len(eng._records) == 1
        assert len(eng._patterns) == 1
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._patterns) == 0


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_patterns"] == 0
        assert stats["quality_threshold"] == 0.7
        assert stats["quality_distribution"] == {}
        assert stats["unique_responders"] == 0

    def test_populated(self):
        eng = _engine()
        eng.record_handoff("INC-1", "alice", "bob")
        eng.record_handoff("INC-2", "bob", "carol")
        eng.detect_patterns()
        stats = eng.get_stats()
        assert stats["total_records"] == 2
        assert stats["total_patterns"] >= 1
        assert stats["unique_responders"] == 3
        assert len(stats["quality_distribution"]) > 0
