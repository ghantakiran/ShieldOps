"""Tests for shieldops.knowledge.knowledge_coverage — KnowledgeCoverageAnalyzer."""

from __future__ import annotations

from shieldops.knowledge.knowledge_coverage import (
    CoverageArea,
    CoverageGapDetail,
    CoverageGapType,
    CoverageLevel,
    CoverageRecord,
    KnowledgeCoverageAnalyzer,
    KnowledgeCoverageReport,
)


def _engine(**kw) -> KnowledgeCoverageAnalyzer:
    return KnowledgeCoverageAnalyzer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_coverage_area_runbooks(self):
        assert CoverageArea.RUNBOOKS == "runbooks"

    def test_coverage_area_playbooks(self):
        assert CoverageArea.PLAYBOOKS == "playbooks"

    def test_coverage_area_documentation(self):
        assert CoverageArea.DOCUMENTATION == "documentation"

    def test_coverage_area_training(self):
        assert CoverageArea.TRAINING == "training"

    def test_coverage_area_troubleshooting(self):
        assert CoverageArea.TROUBLESHOOTING == "troubleshooting"

    def test_coverage_level_comprehensive(self):
        assert CoverageLevel.COMPREHENSIVE == "comprehensive"

    def test_coverage_level_adequate(self):
        assert CoverageLevel.ADEQUATE == "adequate"

    def test_coverage_level_partial(self):
        assert CoverageLevel.PARTIAL == "partial"

    def test_coverage_level_minimal(self):
        assert CoverageLevel.MINIMAL == "minimal"

    def test_coverage_level_none(self):
        assert CoverageLevel.NONE == "none"

    def test_coverage_gap_type_missing_runbook(self):
        assert CoverageGapType.MISSING_RUNBOOK == "missing_runbook"

    def test_coverage_gap_type_outdated_docs(self):
        assert CoverageGapType.OUTDATED_DOCS == "outdated_docs"

    def test_coverage_gap_type_no_training(self):
        assert CoverageGapType.NO_TRAINING == "no_training"

    def test_coverage_gap_type_incomplete_playbook(self):
        assert CoverageGapType.INCOMPLETE_PLAYBOOK == "incomplete_playbook"

    def test_coverage_gap_type_undocumented_service(self):
        assert CoverageGapType.UNDOCUMENTED_SERVICE == "undocumented_service"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_coverage_record_defaults(self):
        r = CoverageRecord()
        assert r.id
        assert r.service_id == ""
        assert r.coverage_area == CoverageArea.RUNBOOKS
        assert r.coverage_level == CoverageLevel.NONE
        assert r.coverage_gap_type == CoverageGapType.MISSING_RUNBOOK
        assert r.coverage_pct == 0.0
        assert r.team == ""
        assert r.created_at > 0

    def test_coverage_gap_detail_defaults(self):
        g = CoverageGapDetail()
        assert g.id
        assert g.gap_pattern == ""
        assert g.coverage_area == CoverageArea.RUNBOOKS
        assert g.severity_score == 0.0
        assert g.affected_services == 0
        assert g.description == ""
        assert g.created_at > 0

    def test_knowledge_coverage_report_defaults(self):
        r = KnowledgeCoverageReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_gaps == 0
        assert r.covered_services == 0
        assert r.avg_coverage_pct == 0.0
        assert r.by_area == {}
        assert r.by_level == {}
        assert r.by_gap_type == {}
        assert r.uncovered == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_coverage
# ---------------------------------------------------------------------------


class TestRecordCoverage:
    def test_basic(self):
        eng = _engine()
        r = eng.record_coverage(
            service_id="SVC-001",
            coverage_area=CoverageArea.PLAYBOOKS,
            coverage_level=CoverageLevel.COMPREHENSIVE,
            coverage_gap_type=CoverageGapType.OUTDATED_DOCS,
            coverage_pct=95.0,
            team="sre",
        )
        assert r.service_id == "SVC-001"
        assert r.coverage_area == CoverageArea.PLAYBOOKS
        assert r.coverage_level == CoverageLevel.COMPREHENSIVE
        assert r.coverage_gap_type == CoverageGapType.OUTDATED_DOCS
        assert r.coverage_pct == 95.0
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_coverage(service_id=f"SVC-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_coverage
# ---------------------------------------------------------------------------


class TestGetCoverage:
    def test_found(self):
        eng = _engine()
        r = eng.record_coverage(
            service_id="SVC-001",
            coverage_area=CoverageArea.DOCUMENTATION,
        )
        result = eng.get_coverage(r.id)
        assert result is not None
        assert result.coverage_area == CoverageArea.DOCUMENTATION

    def test_not_found(self):
        eng = _engine()
        assert eng.get_coverage("nonexistent") is None


# ---------------------------------------------------------------------------
# list_coverages
# ---------------------------------------------------------------------------


class TestListCoverages:
    def test_list_all(self):
        eng = _engine()
        eng.record_coverage(service_id="SVC-001")
        eng.record_coverage(service_id="SVC-002")
        assert len(eng.list_coverages()) == 2

    def test_filter_by_coverage_area(self):
        eng = _engine()
        eng.record_coverage(
            service_id="SVC-001",
            coverage_area=CoverageArea.RUNBOOKS,
        )
        eng.record_coverage(
            service_id="SVC-002",
            coverage_area=CoverageArea.TRAINING,
        )
        results = eng.list_coverages(coverage_area=CoverageArea.RUNBOOKS)
        assert len(results) == 1

    def test_filter_by_coverage_level(self):
        eng = _engine()
        eng.record_coverage(
            service_id="SVC-001",
            coverage_level=CoverageLevel.COMPREHENSIVE,
        )
        eng.record_coverage(
            service_id="SVC-002",
            coverage_level=CoverageLevel.MINIMAL,
        )
        results = eng.list_coverages(coverage_level=CoverageLevel.COMPREHENSIVE)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_coverage(service_id="SVC-001", team="sre")
        eng.record_coverage(service_id="SVC-002", team="platform")
        results = eng.list_coverages(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_coverage(service_id=f"SVC-{i}")
        assert len(eng.list_coverages(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_gap
# ---------------------------------------------------------------------------


class TestAddGap:
    def test_basic(self):
        eng = _engine()
        g = eng.add_gap(
            gap_pattern="missing-runbook-*",
            coverage_area=CoverageArea.TROUBLESHOOTING,
            severity_score=8.5,
            affected_services=3,
            description="Missing troubleshooting guides",
        )
        assert g.gap_pattern == "missing-runbook-*"
        assert g.coverage_area == CoverageArea.TROUBLESHOOTING
        assert g.severity_score == 8.5
        assert g.affected_services == 3

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_gap(gap_pattern=f"gap-{i}")
        assert len(eng._gaps) == 2


# ---------------------------------------------------------------------------
# analyze_coverage_patterns
# ---------------------------------------------------------------------------


class TestAnalyzeCoveragePatterns:
    def test_with_data(self):
        eng = _engine()
        eng.record_coverage(
            service_id="SVC-001",
            coverage_area=CoverageArea.RUNBOOKS,
            coverage_pct=90.0,
        )
        eng.record_coverage(
            service_id="SVC-002",
            coverage_area=CoverageArea.RUNBOOKS,
            coverage_pct=80.0,
        )
        result = eng.analyze_coverage_patterns()
        assert "runbooks" in result
        assert result["runbooks"]["count"] == 2
        assert result["runbooks"]["avg_coverage_pct"] == 85.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_coverage_patterns() == {}


# ---------------------------------------------------------------------------
# identify_coverage_gaps
# ---------------------------------------------------------------------------


class TestIdentifyCoverageGaps:
    def test_detects_gaps(self):
        eng = _engine(min_coverage_pct=80.0)
        eng.record_coverage(
            service_id="SVC-001",
            coverage_pct=50.0,
        )
        eng.record_coverage(
            service_id="SVC-002",
            coverage_pct=95.0,
        )
        results = eng.identify_coverage_gaps()
        assert len(results) == 1
        assert results[0]["service_id"] == "SVC-001"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_coverage_gaps() == []


# ---------------------------------------------------------------------------
# rank_by_coverage_score
# ---------------------------------------------------------------------------


class TestRankByCoverageScore:
    def test_ranked_descending(self):
        eng = _engine()
        eng.record_coverage(service_id="SVC-001", team="sre", coverage_pct=90.0)
        eng.record_coverage(service_id="SVC-002", team="sre", coverage_pct=80.0)
        eng.record_coverage(service_id="SVC-003", team="platform", coverage_pct=50.0)
        results = eng.rank_by_coverage_score()
        assert len(results) == 2
        assert results[0]["team"] == "sre"
        assert results[0]["total_coverage"] == 170.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_coverage_score() == []


# ---------------------------------------------------------------------------
# detect_coverage_trends
# ---------------------------------------------------------------------------


class TestDetectCoverageTrends:
    def test_stable(self):
        eng = _engine()
        for pct in [80.0, 80.0, 80.0, 80.0]:
            eng.record_coverage(service_id="SVC", coverage_pct=pct)
        result = eng.detect_coverage_trends()
        assert result["trend"] == "stable"

    def test_increasing(self):
        eng = _engine()
        for pct in [50.0, 50.0, 90.0, 90.0]:
            eng.record_coverage(service_id="SVC", coverage_pct=pct)
        result = eng.detect_coverage_trends()
        assert result["trend"] == "increasing"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_coverage_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(min_coverage_pct=80.0)
        eng.record_coverage(
            service_id="SVC-001",
            coverage_area=CoverageArea.RUNBOOKS,
            coverage_level=CoverageLevel.PARTIAL,
            coverage_pct=50.0,
            team="sre",
        )
        report = eng.generate_report()
        assert isinstance(report, KnowledgeCoverageReport)
        assert report.total_records == 1
        assert report.avg_coverage_pct == 50.0
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
        eng.record_coverage(service_id="SVC-001")
        eng.add_gap(gap_pattern="g1")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._gaps) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_gaps"] == 0
        assert stats["area_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_coverage(
            service_id="SVC-001",
            coverage_area=CoverageArea.PLAYBOOKS,
            team="sre",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "playbooks" in stats["area_distribution"]
