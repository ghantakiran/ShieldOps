"""Tests for shieldops.knowledge.knowledge_reuse_tracker — KnowledgeReuseTracker."""

from __future__ import annotations

from shieldops.knowledge.knowledge_reuse_tracker import (
    ContentType,
    KnowledgeReuseReport,
    KnowledgeReuseTracker,
    ReuseAnalysis,
    ReuseContext,
    ReuseOutcome,
    ReuseRecord,
)


def _engine(**kw) -> KnowledgeReuseTracker:
    return KnowledgeReuseTracker(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_type_article(self):
        assert ContentType.ARTICLE == "article"

    def test_type_runbook(self):
        assert ContentType.RUNBOOK == "runbook"

    def test_type_playbook(self):
        assert ContentType.PLAYBOOK == "playbook"

    def test_type_postmortem(self):
        assert ContentType.POSTMORTEM == "postmortem"

    def test_type_architecture_doc(self):
        assert ContentType.ARCHITECTURE_DOC == "architecture_doc"

    def test_outcome_resolved_issue(self):
        assert ReuseOutcome.RESOLVED_ISSUE == "resolved_issue"

    def test_outcome_partially_helpful(self):
        assert ReuseOutcome.PARTIALLY_HELPFUL == "partially_helpful"

    def test_outcome_outdated_content(self):
        assert ReuseOutcome.OUTDATED_CONTENT == "outdated_content"

    def test_outcome_not_applicable(self):
        assert ReuseOutcome.NOT_APPLICABLE == "not_applicable"

    def test_outcome_needs_update(self):
        assert ReuseOutcome.NEEDS_UPDATE == "needs_update"

    def test_context_incident_response(self):
        assert ReuseContext.INCIDENT_RESPONSE == "incident_response"

    def test_context_change_planning(self):
        assert ReuseContext.CHANGE_PLANNING == "change_planning"

    def test_context_onboarding(self):
        assert ReuseContext.ONBOARDING == "onboarding"

    def test_context_troubleshooting(self):
        assert ReuseContext.TROUBLESHOOTING == "troubleshooting"

    def test_context_compliance_audit(self):
        assert ReuseContext.COMPLIANCE_AUDIT == "compliance_audit"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_reuse_record_defaults(self):
        r = ReuseRecord()
        assert r.id
        assert r.content_id == ""
        assert r.content_type == ContentType.ARTICLE
        assert r.reuse_outcome == ReuseOutcome.RESOLVED_ISSUE
        assert r.reuse_context == ReuseContext.INCIDENT_RESPONSE
        assert r.reuse_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_reuse_analysis_defaults(self):
        a = ReuseAnalysis()
        assert a.id
        assert a.content_id == ""
        assert a.content_type == ContentType.ARTICLE
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_reuse_report_defaults(self):
        r = KnowledgeReuseReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.low_reuse_count == 0
        assert r.avg_reuse_score == 0.0
        assert r.by_type == {}
        assert r.by_outcome == {}
        assert r.by_context == {}
        assert r.top_low_reuse == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_reuse
# ---------------------------------------------------------------------------


class TestRecordReuse:
    def test_basic(self):
        eng = _engine()
        r = eng.record_reuse(
            content_id="CNT-001",
            content_type=ContentType.RUNBOOK,
            reuse_outcome=ReuseOutcome.RESOLVED_ISSUE,
            reuse_context=ReuseContext.INCIDENT_RESPONSE,
            reuse_score=85.0,
            service="api-gateway",
            team="sre",
        )
        assert r.content_id == "CNT-001"
        assert r.content_type == ContentType.RUNBOOK
        assert r.reuse_outcome == ReuseOutcome.RESOLVED_ISSUE
        assert r.reuse_context == ReuseContext.INCIDENT_RESPONSE
        assert r.reuse_score == 85.0
        assert r.service == "api-gateway"
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_reuse(content_id=f"CNT-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_reuse
# ---------------------------------------------------------------------------


class TestGetReuse:
    def test_found(self):
        eng = _engine()
        r = eng.record_reuse(
            content_id="CNT-001",
            content_type=ContentType.PLAYBOOK,
        )
        result = eng.get_reuse(r.id)
        assert result is not None
        assert result.content_type == ContentType.PLAYBOOK

    def test_not_found(self):
        eng = _engine()
        assert eng.get_reuse("nonexistent") is None


# ---------------------------------------------------------------------------
# list_reuse_records
# ---------------------------------------------------------------------------


class TestListReuseRecords:
    def test_list_all(self):
        eng = _engine()
        eng.record_reuse(content_id="CNT-001")
        eng.record_reuse(content_id="CNT-002")
        assert len(eng.list_reuse_records()) == 2

    def test_filter_by_content_type(self):
        eng = _engine()
        eng.record_reuse(
            content_id="CNT-001",
            content_type=ContentType.ARTICLE,
        )
        eng.record_reuse(
            content_id="CNT-002",
            content_type=ContentType.RUNBOOK,
        )
        results = eng.list_reuse_records(content_type=ContentType.ARTICLE)
        assert len(results) == 1

    def test_filter_by_outcome(self):
        eng = _engine()
        eng.record_reuse(
            content_id="CNT-001",
            reuse_outcome=ReuseOutcome.RESOLVED_ISSUE,
        )
        eng.record_reuse(
            content_id="CNT-002",
            reuse_outcome=ReuseOutcome.OUTDATED_CONTENT,
        )
        results = eng.list_reuse_records(reuse_outcome=ReuseOutcome.RESOLVED_ISSUE)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_reuse(content_id="CNT-001", team="sre")
        eng.record_reuse(content_id="CNT-002", team="platform")
        results = eng.list_reuse_records(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_reuse(content_id=f"CNT-{i}")
        assert len(eng.list_reuse_records(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            content_id="CNT-001",
            content_type=ContentType.POSTMORTEM,
            analysis_score=72.0,
            threshold=70.0,
            breached=True,
            description="Reuse below target",
        )
        assert a.content_id == "CNT-001"
        assert a.content_type == ContentType.POSTMORTEM
        assert a.analysis_score == 72.0
        assert a.threshold == 70.0
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(content_id=f"CNT-{i}")
        assert len(eng._analyses) == 2


# ---------------------------------------------------------------------------
# analyze_reuse_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeReuseDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_reuse(
            content_id="CNT-001",
            content_type=ContentType.ARTICLE,
            reuse_score=80.0,
        )
        eng.record_reuse(
            content_id="CNT-002",
            content_type=ContentType.ARTICLE,
            reuse_score=90.0,
        )
        result = eng.analyze_reuse_distribution()
        assert "article" in result
        assert result["article"]["count"] == 2
        assert result["article"]["avg_reuse_score"] == 85.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_reuse_distribution() == {}


# ---------------------------------------------------------------------------
# identify_low_reuse_content
# ---------------------------------------------------------------------------


class TestIdentifyLowReuseContent:
    def test_detects_low(self):
        eng = _engine(min_reuse_score=50.0)
        eng.record_reuse(
            content_id="CNT-001",
            reuse_score=30.0,
        )
        eng.record_reuse(
            content_id="CNT-002",
            reuse_score=80.0,
        )
        results = eng.identify_low_reuse_content()
        assert len(results) == 1
        assert results[0]["content_id"] == "CNT-001"

    def test_sorted_ascending(self):
        eng = _engine(min_reuse_score=50.0)
        eng.record_reuse(content_id="CNT-001", reuse_score=40.0)
        eng.record_reuse(content_id="CNT-002", reuse_score=20.0)
        results = eng.identify_low_reuse_content()
        assert len(results) == 2
        assert results[0]["reuse_score"] == 20.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_low_reuse_content() == []


# ---------------------------------------------------------------------------
# rank_by_reuse
# ---------------------------------------------------------------------------


class TestRankByReuse:
    def test_ranked_ascending(self):
        eng = _engine()
        eng.record_reuse(content_id="CNT-001", reuse_score=90.0, service="svc-a")
        eng.record_reuse(content_id="CNT-002", reuse_score=50.0, service="svc-b")
        results = eng.rank_by_reuse()
        assert len(results) == 2
        assert results[0]["service"] == "svc-b"
        assert results[0]["avg_reuse_score"] == 50.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_reuse() == []


# ---------------------------------------------------------------------------
# detect_reuse_trends
# ---------------------------------------------------------------------------


class TestDetectReuseTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(content_id="CNT-001", analysis_score=70.0)
        result = eng.detect_reuse_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(content_id="CNT-001", analysis_score=50.0)
        eng.add_analysis(content_id="CNT-002", analysis_score=50.0)
        eng.add_analysis(content_id="CNT-003", analysis_score=80.0)
        eng.add_analysis(content_id="CNT-004", analysis_score=80.0)
        result = eng.detect_reuse_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_reuse_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(min_reuse_score=50.0)
        eng.record_reuse(
            content_id="CNT-001",
            content_type=ContentType.ARTICLE,
            reuse_outcome=ReuseOutcome.OUTDATED_CONTENT,
            reuse_score=30.0,
        )
        report = eng.generate_report()
        assert isinstance(report, KnowledgeReuseReport)
        assert report.total_records == 1
        assert report.low_reuse_count == 1
        assert len(report.top_low_reuse) == 1
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
        eng.record_reuse(content_id="CNT-001")
        eng.add_analysis(content_id="CNT-001")
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
        assert stats["content_type_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_reuse(
            content_id="CNT-001",
            content_type=ContentType.ARTICLE,
            team="sre",
            service="api-gateway",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "article" in stats["content_type_distribution"]
