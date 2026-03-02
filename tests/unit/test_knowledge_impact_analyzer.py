"""Tests for shieldops.knowledge.knowledge_impact_analyzer — KnowledgeImpactAnalyzer."""

from __future__ import annotations

from shieldops.knowledge.knowledge_impact_analyzer import (
    DocumentType,
    ImpactAssessment,
    ImpactCategory,
    ImpactRecord,
    KnowledgeImpactAnalyzer,
    KnowledgeImpactReport,
    RelevanceLevel,
)


def _engine(**kw) -> KnowledgeImpactAnalyzer:
    return KnowledgeImpactAnalyzer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_category_mttr_reduction(self):
        assert ImpactCategory.MTTR_REDUCTION == "mttr_reduction"

    def test_category_toil_elimination(self):
        assert ImpactCategory.TOIL_ELIMINATION == "toil_elimination"

    def test_category_onboarding_speed(self):
        assert ImpactCategory.ONBOARDING_SPEED == "onboarding_speed"

    def test_category_error_prevention(self):
        assert ImpactCategory.ERROR_PREVENTION == "error_prevention"

    def test_category_knowledge_transfer(self):
        assert ImpactCategory.KNOWLEDGE_TRANSFER == "knowledge_transfer"

    def test_doctype_runbook(self):
        assert DocumentType.RUNBOOK == "runbook"

    def test_doctype_playbook(self):
        assert DocumentType.PLAYBOOK == "playbook"

    def test_doctype_architecture_doc(self):
        assert DocumentType.ARCHITECTURE_DOC == "architecture_doc"

    def test_doctype_troubleshooting_guide(self):
        assert DocumentType.TROUBLESHOOTING_GUIDE == "troubleshooting_guide"

    def test_doctype_postmortem(self):
        assert DocumentType.POSTMORTEM == "postmortem"

    def test_relevance_essential(self):
        assert RelevanceLevel.ESSENTIAL == "essential"

    def test_relevance_high(self):
        assert RelevanceLevel.HIGH == "high"

    def test_relevance_moderate(self):
        assert RelevanceLevel.MODERATE == "moderate"

    def test_relevance_low(self):
        assert RelevanceLevel.LOW == "low"

    def test_relevance_obsolete(self):
        assert RelevanceLevel.OBSOLETE == "obsolete"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_impact_record_defaults(self):
        r = ImpactRecord()
        assert r.id
        assert r.document_id == ""
        assert r.impact_category == ImpactCategory.MTTR_REDUCTION
        assert r.document_type == DocumentType.RUNBOOK
        assert r.relevance_level == RelevanceLevel.ESSENTIAL
        assert r.impact_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_impact_assessment_defaults(self):
        a = ImpactAssessment()
        assert a.id
        assert a.document_id == ""
        assert a.impact_category == ImpactCategory.MTTR_REDUCTION
        assert a.assessment_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_impact_report_defaults(self):
        r = KnowledgeImpactReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_assessments == 0
        assert r.low_impact_count == 0
        assert r.avg_impact_score == 0.0
        assert r.by_category == {}
        assert r.by_type == {}
        assert r.by_relevance == {}
        assert r.top_low_impact == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_impact
# ---------------------------------------------------------------------------


class TestRecordImpact:
    def test_basic(self):
        eng = _engine()
        r = eng.record_impact(
            document_id="DOC-001",
            impact_category=ImpactCategory.MTTR_REDUCTION,
            document_type=DocumentType.RUNBOOK,
            relevance_level=RelevanceLevel.ESSENTIAL,
            impact_score=85.0,
            service="api-gateway",
            team="sre",
        )
        assert r.document_id == "DOC-001"
        assert r.impact_category == ImpactCategory.MTTR_REDUCTION
        assert r.document_type == DocumentType.RUNBOOK
        assert r.relevance_level == RelevanceLevel.ESSENTIAL
        assert r.impact_score == 85.0
        assert r.service == "api-gateway"
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_impact(document_id=f"DOC-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_impact
# ---------------------------------------------------------------------------


class TestGetImpact:
    def test_found(self):
        eng = _engine()
        r = eng.record_impact(
            document_id="DOC-001",
            document_type=DocumentType.PLAYBOOK,
        )
        result = eng.get_impact(r.id)
        assert result is not None
        assert result.document_type == DocumentType.PLAYBOOK

    def test_not_found(self):
        eng = _engine()
        assert eng.get_impact("nonexistent") is None


# ---------------------------------------------------------------------------
# list_impacts
# ---------------------------------------------------------------------------


class TestListImpacts:
    def test_list_all(self):
        eng = _engine()
        eng.record_impact(document_id="DOC-001")
        eng.record_impact(document_id="DOC-002")
        assert len(eng.list_impacts()) == 2

    def test_filter_by_impact_category(self):
        eng = _engine()
        eng.record_impact(
            document_id="DOC-001",
            impact_category=ImpactCategory.MTTR_REDUCTION,
        )
        eng.record_impact(
            document_id="DOC-002",
            impact_category=ImpactCategory.TOIL_ELIMINATION,
        )
        results = eng.list_impacts(impact_category=ImpactCategory.MTTR_REDUCTION)
        assert len(results) == 1

    def test_filter_by_document_type(self):
        eng = _engine()
        eng.record_impact(
            document_id="DOC-001",
            document_type=DocumentType.RUNBOOK,
        )
        eng.record_impact(
            document_id="DOC-002",
            document_type=DocumentType.POSTMORTEM,
        )
        results = eng.list_impacts(document_type=DocumentType.RUNBOOK)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_impact(document_id="DOC-001", team="sre")
        eng.record_impact(document_id="DOC-002", team="platform")
        results = eng.list_impacts(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_impact(document_id=f"DOC-{i}")
        assert len(eng.list_impacts(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_assessment
# ---------------------------------------------------------------------------


class TestAddAssessment:
    def test_basic(self):
        eng = _engine()
        a = eng.add_assessment(
            document_id="DOC-001",
            impact_category=ImpactCategory.TOIL_ELIMINATION,
            assessment_score=72.0,
            threshold=70.0,
            breached=True,
            description="Impact below target",
        )
        assert a.document_id == "DOC-001"
        assert a.impact_category == ImpactCategory.TOIL_ELIMINATION
        assert a.assessment_score == 72.0
        assert a.threshold == 70.0
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_assessment(document_id=f"DOC-{i}")
        assert len(eng._assessments) == 2


# ---------------------------------------------------------------------------
# analyze_impact_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeImpactDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_impact(
            document_id="DOC-001",
            impact_category=ImpactCategory.MTTR_REDUCTION,
            impact_score=80.0,
        )
        eng.record_impact(
            document_id="DOC-002",
            impact_category=ImpactCategory.MTTR_REDUCTION,
            impact_score=90.0,
        )
        result = eng.analyze_impact_distribution()
        assert "mttr_reduction" in result
        assert result["mttr_reduction"]["count"] == 2
        assert result["mttr_reduction"]["avg_impact_score"] == 85.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_impact_distribution() == {}


# ---------------------------------------------------------------------------
# identify_low_impact_docs
# ---------------------------------------------------------------------------


class TestIdentifyLowImpactDocs:
    def test_detects_low(self):
        eng = _engine(impact_relevance_threshold=65.0)
        eng.record_impact(
            document_id="DOC-001",
            impact_score=30.0,
        )
        eng.record_impact(
            document_id="DOC-002",
            impact_score=80.0,
        )
        results = eng.identify_low_impact_docs()
        assert len(results) == 1
        assert results[0]["document_id"] == "DOC-001"

    def test_sorted_ascending(self):
        eng = _engine(impact_relevance_threshold=65.0)
        eng.record_impact(document_id="DOC-001", impact_score=40.0)
        eng.record_impact(document_id="DOC-002", impact_score=20.0)
        results = eng.identify_low_impact_docs()
        assert len(results) == 2
        assert results[0]["impact_score"] == 20.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_low_impact_docs() == []


# ---------------------------------------------------------------------------
# rank_by_impact
# ---------------------------------------------------------------------------


class TestRankByImpact:
    def test_ranked_ascending(self):
        eng = _engine()
        eng.record_impact(document_id="DOC-001", impact_score=90.0, service="svc-a")
        eng.record_impact(document_id="DOC-002", impact_score=50.0, service="svc-b")
        results = eng.rank_by_impact()
        assert len(results) == 2
        assert results[0]["service"] == "svc-b"
        assert results[0]["avg_impact_score"] == 50.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_impact() == []


# ---------------------------------------------------------------------------
# detect_impact_trends
# ---------------------------------------------------------------------------


class TestDetectImpactTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_assessment(document_id="DOC-001", assessment_score=70.0)
        result = eng.detect_impact_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_assessment(document_id="DOC-001", assessment_score=50.0)
        eng.add_assessment(document_id="DOC-002", assessment_score=50.0)
        eng.add_assessment(document_id="DOC-003", assessment_score=80.0)
        eng.add_assessment(document_id="DOC-004", assessment_score=80.0)
        result = eng.detect_impact_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_impact_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(impact_relevance_threshold=65.0)
        eng.record_impact(
            document_id="DOC-001",
            impact_category=ImpactCategory.MTTR_REDUCTION,
            document_type=DocumentType.RUNBOOK,
            impact_score=30.0,
        )
        report = eng.generate_report()
        assert isinstance(report, KnowledgeImpactReport)
        assert report.total_records == 1
        assert report.low_impact_count == 1
        assert len(report.top_low_impact) == 1
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
        eng.record_impact(document_id="DOC-001")
        eng.add_assessment(document_id="DOC-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._assessments) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_assessments"] == 0
        assert stats["impact_category_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_impact(
            document_id="DOC-001",
            impact_category=ImpactCategory.MTTR_REDUCTION,
            team="sre",
            service="api-gateway",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "mttr_reduction" in stats["impact_category_distribution"]
