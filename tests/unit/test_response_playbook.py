"""Tests for shieldops.incidents.response_playbook — IncidentResponsePlaybookManager."""

from __future__ import annotations

from shieldops.incidents.response_playbook import (
    IncidentResponsePlaybookManager,
    PlaybookEffectiveness,
    PlaybookRecord,
    PlaybookStatus,
    PlaybookType,
    PlaybookUsage,
    ResponsePlaybookReport,
)


def _engine(**kw) -> IncidentResponsePlaybookManager:
    return IncidentResponsePlaybookManager(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_type_automated(self):
        assert PlaybookType.AUTOMATED == "automated"

    def test_type_semi_automated(self):
        assert PlaybookType.SEMI_AUTOMATED == "semi_automated"

    def test_type_manual(self):
        assert PlaybookType.MANUAL == "manual"

    def test_type_escalation(self):
        assert PlaybookType.ESCALATION == "escalation"

    def test_type_communication(self):
        assert PlaybookType.COMMUNICATION == "communication"

    def test_status_active(self):
        assert PlaybookStatus.ACTIVE == "active"

    def test_status_draft(self):
        assert PlaybookStatus.DRAFT == "draft"

    def test_status_deprecated(self):
        assert PlaybookStatus.DEPRECATED == "deprecated"

    def test_status_under_review(self):
        assert PlaybookStatus.UNDER_REVIEW == "under_review"

    def test_status_archived(self):
        assert PlaybookStatus.ARCHIVED == "archived"

    def test_effectiveness_highly_effective(self):
        assert PlaybookEffectiveness.HIGHLY_EFFECTIVE == "highly_effective"

    def test_effectiveness_effective(self):
        assert PlaybookEffectiveness.EFFECTIVE == "effective"

    def test_effectiveness_needs_improvement(self):
        assert PlaybookEffectiveness.NEEDS_IMPROVEMENT == "needs_improvement"

    def test_effectiveness_ineffective(self):
        assert PlaybookEffectiveness.INEFFECTIVE == "ineffective"

    def test_effectiveness_untested(self):
        assert PlaybookEffectiveness.UNTESTED == "untested"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_playbook_record_defaults(self):
        r = PlaybookRecord()
        assert r.id
        assert r.playbook_name == ""
        assert r.playbook_type == PlaybookType.MANUAL
        assert r.playbook_status == PlaybookStatus.DRAFT
        assert r.playbook_effectiveness == PlaybookEffectiveness.UNTESTED
        assert r.coverage_score == 0.0
        assert r.team == ""
        assert r.created_at > 0

    def test_playbook_usage_defaults(self):
        u = PlaybookUsage()
        assert u.id
        assert u.usage_name == ""
        assert u.playbook_type == PlaybookType.MANUAL
        assert u.execution_count == 0
        assert u.avg_resolution_time == 0.0
        assert u.description == ""
        assert u.created_at > 0

    def test_response_playbook_report_defaults(self):
        r = ResponsePlaybookReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_usages == 0
        assert r.low_coverage_playbooks == 0
        assert r.avg_coverage_score == 0.0
        assert r.by_type == {}
        assert r.by_status == {}
        assert r.by_effectiveness == {}
        assert r.top_items == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_playbook
# ---------------------------------------------------------------------------


class TestRecordPlaybook:
    def test_basic(self):
        eng = _engine()
        r = eng.record_playbook(
            playbook_name="restart-service",
            playbook_type=PlaybookType.AUTOMATED,
            playbook_status=PlaybookStatus.ACTIVE,
            playbook_effectiveness=PlaybookEffectiveness.HIGHLY_EFFECTIVE,
            coverage_score=90.0,
            team="sre",
        )
        assert r.playbook_name == "restart-service"
        assert r.playbook_type == PlaybookType.AUTOMATED
        assert r.playbook_status == PlaybookStatus.ACTIVE
        assert r.playbook_effectiveness == PlaybookEffectiveness.HIGHLY_EFFECTIVE
        assert r.coverage_score == 90.0
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_playbook(playbook_name=f"pb-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_playbook
# ---------------------------------------------------------------------------


class TestGetPlaybook:
    def test_found(self):
        eng = _engine()
        r = eng.record_playbook(
            playbook_name="restart-service",
            playbook_type=PlaybookType.AUTOMATED,
        )
        result = eng.get_playbook(r.id)
        assert result is not None
        assert result.playbook_type == PlaybookType.AUTOMATED

    def test_not_found(self):
        eng = _engine()
        assert eng.get_playbook("nonexistent") is None


# ---------------------------------------------------------------------------
# list_playbooks
# ---------------------------------------------------------------------------


class TestListPlaybooks:
    def test_list_all(self):
        eng = _engine()
        eng.record_playbook(playbook_name="pb-1")
        eng.record_playbook(playbook_name="pb-2")
        assert len(eng.list_playbooks()) == 2

    def test_filter_by_type(self):
        eng = _engine()
        eng.record_playbook(
            playbook_name="pb-1",
            playbook_type=PlaybookType.AUTOMATED,
        )
        eng.record_playbook(
            playbook_name="pb-2",
            playbook_type=PlaybookType.MANUAL,
        )
        results = eng.list_playbooks(playbook_type=PlaybookType.AUTOMATED)
        assert len(results) == 1

    def test_filter_by_status(self):
        eng = _engine()
        eng.record_playbook(
            playbook_name="pb-1",
            playbook_status=PlaybookStatus.ACTIVE,
        )
        eng.record_playbook(
            playbook_name="pb-2",
            playbook_status=PlaybookStatus.DEPRECATED,
        )
        results = eng.list_playbooks(status=PlaybookStatus.ACTIVE)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_playbook(playbook_name="pb-1", team="sre")
        eng.record_playbook(playbook_name="pb-2", team="platform")
        results = eng.list_playbooks(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_playbook(playbook_name=f"pb-{i}")
        assert len(eng.list_playbooks(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_usage
# ---------------------------------------------------------------------------


class TestAddUsage:
    def test_basic(self):
        eng = _engine()
        u = eng.add_usage(
            usage_name="restart-usage",
            playbook_type=PlaybookType.AUTOMATED,
            execution_count=15,
            avg_resolution_time=12.5,
            description="Service restart usage",
        )
        assert u.usage_name == "restart-usage"
        assert u.playbook_type == PlaybookType.AUTOMATED
        assert u.execution_count == 15
        assert u.avg_resolution_time == 12.5

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_usage(usage_name=f"usage-{i}")
        assert len(eng._usages) == 2


# ---------------------------------------------------------------------------
# analyze_playbook_coverage
# ---------------------------------------------------------------------------


class TestAnalyzePlaybookCoverage:
    def test_with_data(self):
        eng = _engine()
        eng.record_playbook(
            playbook_name="pb-1",
            playbook_type=PlaybookType.AUTOMATED,
            coverage_score=90.0,
        )
        eng.record_playbook(
            playbook_name="pb-2",
            playbook_type=PlaybookType.AUTOMATED,
            coverage_score=80.0,
        )
        result = eng.analyze_playbook_coverage()
        assert "automated" in result
        assert result["automated"]["count"] == 2
        assert result["automated"]["avg_coverage_score"] == 85.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_playbook_coverage() == {}


# ---------------------------------------------------------------------------
# identify_gaps
# ---------------------------------------------------------------------------


class TestIdentifyGaps:
    def test_detects_ineffective(self):
        eng = _engine()
        eng.record_playbook(
            playbook_name="pb-1",
            playbook_effectiveness=PlaybookEffectiveness.INEFFECTIVE,
            coverage_score=20.0,
        )
        eng.record_playbook(
            playbook_name="pb-2",
            playbook_effectiveness=PlaybookEffectiveness.HIGHLY_EFFECTIVE,
        )
        results = eng.identify_gaps()
        assert len(results) == 1
        assert results[0]["playbook_name"] == "pb-1"

    def test_detects_untested(self):
        eng = _engine()
        eng.record_playbook(
            playbook_name="pb-1",
            playbook_effectiveness=PlaybookEffectiveness.UNTESTED,
        )
        results = eng.identify_gaps()
        assert len(results) == 1

    def test_empty(self):
        eng = _engine()
        assert eng.identify_gaps() == []


# ---------------------------------------------------------------------------
# rank_by_effectiveness
# ---------------------------------------------------------------------------


class TestRankByEffectiveness:
    def test_ranked_descending(self):
        eng = _engine()
        eng.record_playbook(playbook_name="pb-1", team="sre", coverage_score=90.0)
        eng.record_playbook(playbook_name="pb-2", team="sre", coverage_score=80.0)
        eng.record_playbook(playbook_name="pb-3", team="platform", coverage_score=70.0)
        results = eng.rank_by_effectiveness()
        assert len(results) == 2
        assert results[0]["team"] == "sre"
        assert results[0]["avg_coverage_score"] == 85.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_effectiveness() == []


# ---------------------------------------------------------------------------
# detect_playbook_trends
# ---------------------------------------------------------------------------


class TestDetectPlaybookTrends:
    def test_stable(self):
        eng = _engine()
        for s in [80.0, 80.0, 80.0, 80.0]:
            eng.add_usage(usage_name="u", avg_resolution_time=s)
        result = eng.detect_playbook_trends()
        assert result["trend"] == "stable"

    def test_increasing(self):
        eng = _engine()
        for s in [50.0, 50.0, 90.0, 90.0]:
            eng.add_usage(usage_name="u", avg_resolution_time=s)
        result = eng.detect_playbook_trends()
        assert result["trend"] == "increasing"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_playbook_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_playbook(
            playbook_name="pb-1",
            playbook_type=PlaybookType.AUTOMATED,
            playbook_status=PlaybookStatus.ACTIVE,
            playbook_effectiveness=PlaybookEffectiveness.UNTESTED,
            coverage_score=85.0,
            team="sre",
        )
        report = eng.generate_report()
        assert isinstance(report, ResponsePlaybookReport)
        assert report.total_records == 1
        assert report.low_coverage_playbooks == 1
        assert report.avg_coverage_score == 85.0
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "within acceptable limits" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_playbook(playbook_name="pb-1")
        eng.add_usage(usage_name="u1")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._usages) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_usages"] == 0
        assert stats["type_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_playbook(
            playbook_name="pb-1",
            playbook_type=PlaybookType.AUTOMATED,
            team="sre",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_playbooks"] == 1
        assert "automated" in stats["type_distribution"]
