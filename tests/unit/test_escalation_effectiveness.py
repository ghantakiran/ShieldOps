"""Tests for shieldops.incidents.escalation_effectiveness — EscalationEffectivenessTracker."""

from __future__ import annotations

from shieldops.incidents.escalation_effectiveness import (
    AcknowledgmentSpeed,
    EscalationEffectivenessRecord,
    EscalationEffectivenessReport,
    EscalationEffectivenessTracker,
    EscalationResult,
    ResponderProfile,
    ResponderTier,
)


def _engine(**kw) -> EscalationEffectivenessTracker:
    return EscalationEffectivenessTracker(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    # EscalationResult (5)
    def test_result_resolved(self):
        assert EscalationResult.RESOLVED == "resolved"

    def test_result_partially_resolved(self):
        assert EscalationResult.PARTIALLY_RESOLVED == "partially_resolved"

    def test_result_re_escalated(self):
        assert EscalationResult.RE_ESCALATED == "re_escalated"

    def test_result_timed_out(self):
        assert EscalationResult.TIMED_OUT == "timed_out"

    def test_result_false_escalation(self):
        assert EscalationResult.FALSE_ESCALATION == "false_escalation"

    # ResponderTier (5)
    def test_tier_1(self):
        assert ResponderTier.TIER_1 == "tier_1"

    def test_tier_2(self):
        assert ResponderTier.TIER_2 == "tier_2"

    def test_tier_3(self):
        assert ResponderTier.TIER_3 == "tier_3"

    def test_tier_management(self):
        assert ResponderTier.MANAGEMENT == "management"

    def test_tier_vendor(self):
        assert ResponderTier.VENDOR == "vendor"

    # AcknowledgmentSpeed (5)
    def test_speed_immediate(self):
        assert AcknowledgmentSpeed.IMMEDIATE == "immediate"

    def test_speed_fast(self):
        assert AcknowledgmentSpeed.FAST == "fast"

    def test_speed_normal(self):
        assert AcknowledgmentSpeed.NORMAL == "normal"

    def test_speed_slow(self):
        assert AcknowledgmentSpeed.SLOW == "slow"

    def test_speed_missed(self):
        assert AcknowledgmentSpeed.MISSED == "missed"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_escalation_effectiveness_record_defaults(self):
        r = EscalationEffectivenessRecord()
        assert r.id
        assert r.incident_id == ""
        assert r.responder_id == ""
        assert r.responder_tier == ResponderTier.TIER_1
        assert r.result == EscalationResult.RESOLVED
        assert r.ack_speed == AcknowledgmentSpeed.NORMAL
        assert r.ack_time_minutes == 0.0
        assert r.resolution_time_minutes == 0.0
        assert r.was_correct_target is True
        assert r.created_at > 0

    def test_responder_profile_defaults(self):
        p = ResponderProfile()
        assert p.id
        assert p.responder_id == ""
        assert p.tier == ResponderTier.TIER_1
        assert p.total_escalations == 0
        assert p.resolved_count == 0
        assert p.avg_ack_minutes == 0.0
        assert p.avg_resolution_minutes == 0.0
        assert p.effectiveness_score == 0.0
        assert p.created_at > 0

    def test_escalation_effectiveness_report_defaults(self):
        r = EscalationEffectivenessReport()
        assert r.total_escalations == 0
        assert r.resolved_count == 0
        assert r.false_escalation_count == 0
        assert r.false_escalation_rate_pct == 0.0
        assert r.by_result == {}
        assert r.by_tier == {}
        assert r.top_responders == []
        assert r.recommendations == []
        assert r.generated_at > 0


# ---------------------------------------------------------------------------
# record_escalation
# ---------------------------------------------------------------------------


class TestRecordEscalation:
    def test_basic(self):
        eng = _engine()
        r = eng.record_escalation(
            incident_id="inc-1",
            responder_id="resp-1",
        )
        assert r.incident_id == "inc-1"
        assert r.responder_id == "resp-1"
        assert r.ack_speed == AcknowledgmentSpeed.NORMAL
        assert r.ack_time_minutes == 5.0

    def test_with_params(self):
        eng = _engine()
        r = eng.record_escalation(
            incident_id="inc-2",
            responder_id="resp-2",
            responder_tier=ResponderTier.TIER_3,
            result=EscalationResult.RE_ESCALATED,
            ack_time_minutes=1.0,
            resolution_time_minutes=120.0,
            was_correct_target=False,
        )
        assert r.responder_tier == ResponderTier.TIER_3
        assert r.result == EscalationResult.RE_ESCALATED
        assert r.ack_speed == AcknowledgmentSpeed.IMMEDIATE
        assert r.ack_time_minutes == 1.0
        assert r.resolution_time_minutes == 120.0
        assert r.was_correct_target is False

    def test_slow_ack_speed(self):
        eng = _engine()
        r = eng.record_escalation(
            incident_id="inc-3",
            responder_id="resp-3",
            ack_time_minutes=25.0,
        )
        assert r.ack_speed == AcknowledgmentSpeed.SLOW

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_escalation(
                incident_id=f"inc-{i}",
                responder_id=f"resp-{i}",
            )
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_escalation
# ---------------------------------------------------------------------------


class TestGetEscalation:
    def test_found(self):
        eng = _engine()
        r = eng.record_escalation(
            incident_id="inc-1",
            responder_id="resp-1",
        )
        result = eng.get_escalation(r.id)
        assert result is not None
        assert result.incident_id == "inc-1"

    def test_not_found(self):
        eng = _engine()
        assert eng.get_escalation("nonexistent") is None


# ---------------------------------------------------------------------------
# list_escalations
# ---------------------------------------------------------------------------


class TestListEscalations:
    def test_list_all(self):
        eng = _engine()
        eng.record_escalation(incident_id="inc-1", responder_id="resp-1")
        eng.record_escalation(incident_id="inc-2", responder_id="resp-2")
        assert len(eng.list_escalations()) == 2

    def test_filter_by_responder_id(self):
        eng = _engine()
        eng.record_escalation(incident_id="inc-1", responder_id="resp-1")
        eng.record_escalation(incident_id="inc-2", responder_id="resp-2")
        results = eng.list_escalations(responder_id="resp-1")
        assert len(results) == 1
        assert results[0].responder_id == "resp-1"

    def test_filter_by_result(self):
        eng = _engine()
        eng.record_escalation(
            incident_id="inc-1",
            responder_id="resp-1",
            result=EscalationResult.RESOLVED,
        )
        eng.record_escalation(
            incident_id="inc-2",
            responder_id="resp-2",
            result=EscalationResult.FALSE_ESCALATION,
        )
        results = eng.list_escalations(result=EscalationResult.FALSE_ESCALATION)
        assert len(results) == 1
        assert results[0].result == EscalationResult.FALSE_ESCALATION


# ---------------------------------------------------------------------------
# build_responder_profile
# ---------------------------------------------------------------------------


class TestBuildResponderProfile:
    def test_with_records(self):
        eng = _engine()
        eng.record_escalation(
            incident_id="inc-1",
            responder_id="resp-1",
            result=EscalationResult.RESOLVED,
            ack_time_minutes=3.0,
            resolution_time_minutes=20.0,
        )
        profile = eng.build_responder_profile("resp-1")
        assert profile.responder_id == "resp-1"
        assert profile.total_escalations == 1
        assert profile.resolved_count == 1
        assert profile.avg_ack_minutes == 3.0
        assert profile.avg_resolution_minutes == 20.0
        assert profile.effectiveness_score > 0

    def test_no_records(self):
        eng = _engine()
        profile = eng.build_responder_profile("resp-unknown")
        assert profile.responder_id == "resp-unknown"
        assert profile.total_escalations == 0
        assert profile.effectiveness_score == 0.0


# ---------------------------------------------------------------------------
# calculate_effectiveness_score
# ---------------------------------------------------------------------------


class TestCalculateEffectivenessScore:
    def test_valid(self):
        eng = _engine()
        eng.record_escalation(
            incident_id="inc-1",
            responder_id="resp-1",
            result=EscalationResult.RESOLVED,
            ack_time_minutes=3.0,
            resolution_time_minutes=20.0,
        )
        result = eng.calculate_effectiveness_score("resp-1")
        assert result["responder_id"] == "resp-1"
        assert result["effectiveness_score"] > 0
        assert result["total_escalations"] == 1
        assert result["resolved_count"] == 1

    def test_no_records(self):
        eng = _engine()
        result = eng.calculate_effectiveness_score("resp-unknown")
        assert result["responder_id"] == "resp-unknown"
        assert result["effectiveness_score"] == 0.0
        assert result["total_escalations"] == 0


# ---------------------------------------------------------------------------
# identify_false_escalations
# ---------------------------------------------------------------------------


class TestIdentifyFalseEscalations:
    def test_has_false(self):
        eng = _engine()
        eng.record_escalation(
            incident_id="inc-1",
            responder_id="resp-1",
            result=EscalationResult.FALSE_ESCALATION,
        )
        eng.record_escalation(
            incident_id="inc-2",
            responder_id="resp-2",
            result=EscalationResult.RESOLVED,
        )
        results = eng.identify_false_escalations()
        assert len(results) == 1
        assert results[0]["incident_id"] == "inc-1"
        assert results[0]["responder_tier"] == "tier_1"

    def test_no_false(self):
        eng = _engine()
        eng.record_escalation(
            incident_id="inc-1",
            responder_id="resp-1",
            result=EscalationResult.RESOLVED,
        )
        results = eng.identify_false_escalations()
        assert results == []


# ---------------------------------------------------------------------------
# rank_responders_by_effectiveness
# ---------------------------------------------------------------------------


class TestRankRespondersByEffectiveness:
    def test_ranking(self):
        eng = _engine()
        eng.record_escalation(
            incident_id="inc-1",
            responder_id="resp-1",
            result=EscalationResult.RESOLVED,
            ack_time_minutes=2.0,
        )
        eng.record_escalation(
            incident_id="inc-2",
            responder_id="resp-2",
            result=EscalationResult.TIMED_OUT,
            ack_time_minutes=40.0,
        )
        ranked = eng.rank_responders_by_effectiveness()
        assert len(ranked) == 2
        assert ranked[0]["responder_id"] == "resp-1"
        assert ranked[0]["effectiveness_score"] >= ranked[1]["effectiveness_score"]

    def test_empty(self):
        eng = _engine()
        ranked = eng.rank_responders_by_effectiveness()
        assert ranked == []


# ---------------------------------------------------------------------------
# detect_re_escalation_patterns
# ---------------------------------------------------------------------------


class TestDetectReEscalationPatterns:
    def test_pattern_found(self):
        eng = _engine()
        eng.record_escalation(
            incident_id="inc-1",
            responder_id="resp-1",
            result=EscalationResult.RE_ESCALATED,
        )
        eng.record_escalation(
            incident_id="inc-1",
            responder_id="resp-2",
            result=EscalationResult.RE_ESCALATED,
        )
        patterns = eng.detect_re_escalation_patterns()
        assert len(patterns) == 1
        assert patterns[0]["incident_id"] == "inc-1"
        assert patterns[0]["re_escalation_count"] == 2

    def test_no_pattern(self):
        eng = _engine()
        eng.record_escalation(
            incident_id="inc-1",
            responder_id="resp-1",
            result=EscalationResult.RESOLVED,
        )
        patterns = eng.detect_re_escalation_patterns()
        assert patterns == []


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_escalation(
            incident_id="inc-1",
            responder_id="resp-1",
            result=EscalationResult.RESOLVED,
        )
        eng.record_escalation(
            incident_id="inc-2",
            responder_id="resp-2",
            result=EscalationResult.FALSE_ESCALATION,
        )
        report = eng.generate_report()
        assert isinstance(report, EscalationEffectivenessReport)
        assert report.total_escalations == 2
        assert report.resolved_count == 1
        assert report.false_escalation_count == 1
        assert report.false_escalation_rate_pct == 50.0
        assert len(report.by_result) == 2
        assert len(report.by_tier) > 0
        assert len(report.top_responders) > 0
        assert len(report.recommendations) > 0
        assert report.generated_at > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_escalations == 0
        assert report.resolved_count == 0
        assert "Escalation effectiveness within normal parameters" in report.recommendations


# ---------------------------------------------------------------------------
# clear_data
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_escalation(
            incident_id="inc-1",
            responder_id="resp-1",
        )
        eng.build_responder_profile("resp-1")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._profiles) == 0


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_escalations"] == 0
        assert stats["total_profiles"] == 0
        assert stats["result_distribution"] == {}
        assert stats["unique_responders"] == 0

    def test_populated(self):
        eng = _engine()
        eng.record_escalation(
            incident_id="inc-1",
            responder_id="resp-1",
        )
        eng.build_responder_profile("resp-1")
        stats = eng.get_stats()
        assert stats["total_escalations"] == 1
        assert stats["total_profiles"] == 1
        assert stats["false_rate_threshold"] == 20.0
        assert "resolved" in stats["result_distribution"]
        assert stats["unique_responders"] == 1
