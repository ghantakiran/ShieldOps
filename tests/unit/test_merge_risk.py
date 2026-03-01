"""Tests for shieldops.changes.merge_risk — MergeRiskAssessor."""

from __future__ import annotations

from shieldops.changes.merge_risk import (
    MergeOutcome,
    MergeRiskAssessor,
    MergeRiskRecord,
    MergeRiskReport,
    RiskAssessment,
    RiskFactor,
    RiskLevel,
)


def _engine(**kw) -> MergeRiskAssessor:
    return MergeRiskAssessor(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_factor_change_size(self):
        assert RiskFactor.CHANGE_SIZE == "change_size"

    def test_factor_test_coverage(self):
        assert RiskFactor.TEST_COVERAGE == "test_coverage"

    def test_factor_file_complexity(self):
        assert RiskFactor.FILE_COMPLEXITY == "file_complexity"

    def test_factor_reviewer_familiarity(self):
        assert RiskFactor.REVIEWER_FAMILIARITY == "reviewer_familiarity"

    def test_factor_deployment_window(self):
        assert RiskFactor.DEPLOYMENT_WINDOW == "deployment_window"

    def test_level_critical(self):
        assert RiskLevel.CRITICAL == "critical"

    def test_level_high(self):
        assert RiskLevel.HIGH == "high"

    def test_level_moderate(self):
        assert RiskLevel.MODERATE == "moderate"

    def test_level_low(self):
        assert RiskLevel.LOW == "low"

    def test_level_minimal(self):
        assert RiskLevel.MINIMAL == "minimal"

    def test_outcome_clean(self):
        assert MergeOutcome.CLEAN == "clean"

    def test_outcome_conflict_resolved(self):
        assert MergeOutcome.CONFLICT_RESOLVED == "conflict_resolved"

    def test_outcome_reverted(self):
        assert MergeOutcome.REVERTED == "reverted"

    def test_outcome_caused_incident(self):
        assert MergeOutcome.CAUSED_INCIDENT == "caused_incident"

    def test_outcome_delayed(self):
        assert MergeOutcome.DELAYED == "delayed"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_merge_risk_record_defaults(self):
        r = MergeRiskRecord()
        assert r.id
        assert r.merge_id == ""
        assert r.risk_factor == RiskFactor.CHANGE_SIZE
        assert r.risk_level == RiskLevel.LOW
        assert r.merge_outcome == MergeOutcome.CLEAN
        assert r.risk_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_risk_assessment_defaults(self):
        a = RiskAssessment()
        assert a.id
        assert a.merge_id == ""
        assert a.risk_factor == RiskFactor.CHANGE_SIZE
        assert a.value == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_merge_risk_report_defaults(self):
        r = MergeRiskReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_assessments == 0
        assert r.high_risk_merges == 0
        assert r.avg_risk_score == 0.0
        assert r.by_factor == {}
        assert r.by_level == {}
        assert r.by_outcome == {}
        assert r.top_risky == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_merge
# ---------------------------------------------------------------------------


class TestRecordMerge:
    def test_basic(self):
        eng = _engine()
        r = eng.record_merge(
            merge_id="MR-001",
            risk_factor=RiskFactor.TEST_COVERAGE,
            risk_level=RiskLevel.HIGH,
            merge_outcome=MergeOutcome.CONFLICT_RESOLVED,
            risk_score=65.0,
            service="api-gateway",
            team="sre",
        )
        assert r.merge_id == "MR-001"
        assert r.risk_factor == RiskFactor.TEST_COVERAGE
        assert r.risk_level == RiskLevel.HIGH
        assert r.merge_outcome == MergeOutcome.CONFLICT_RESOLVED
        assert r.risk_score == 65.0
        assert r.service == "api-gateway"
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_merge(merge_id=f"MR-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_merge
# ---------------------------------------------------------------------------


class TestGetMerge:
    def test_found(self):
        eng = _engine()
        r = eng.record_merge(
            merge_id="MR-001",
            risk_level=RiskLevel.CRITICAL,
        )
        result = eng.get_merge(r.id)
        assert result is not None
        assert result.risk_level == RiskLevel.CRITICAL

    def test_not_found(self):
        eng = _engine()
        assert eng.get_merge("nonexistent") is None


# ---------------------------------------------------------------------------
# list_merges
# ---------------------------------------------------------------------------


class TestListMerges:
    def test_list_all(self):
        eng = _engine()
        eng.record_merge(merge_id="MR-001")
        eng.record_merge(merge_id="MR-002")
        assert len(eng.list_merges()) == 2

    def test_filter_by_factor(self):
        eng = _engine()
        eng.record_merge(
            merge_id="MR-001",
            risk_factor=RiskFactor.FILE_COMPLEXITY,
        )
        eng.record_merge(
            merge_id="MR-002",
            risk_factor=RiskFactor.CHANGE_SIZE,
        )
        results = eng.list_merges(factor=RiskFactor.FILE_COMPLEXITY)
        assert len(results) == 1

    def test_filter_by_level(self):
        eng = _engine()
        eng.record_merge(
            merge_id="MR-001",
            risk_level=RiskLevel.CRITICAL,
        )
        eng.record_merge(
            merge_id="MR-002",
            risk_level=RiskLevel.LOW,
        )
        results = eng.list_merges(level=RiskLevel.CRITICAL)
        assert len(results) == 1

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_merge(merge_id="MR-001", service="api")
        eng.record_merge(merge_id="MR-002", service="web")
        results = eng.list_merges(service="api")
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_merge(merge_id="MR-001", team="sre")
        eng.record_merge(merge_id="MR-002", team="platform")
        results = eng.list_merges(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_merge(merge_id=f"MR-{i}")
        assert len(eng.list_merges(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_assessment
# ---------------------------------------------------------------------------


class TestAddAssessment:
    def test_basic(self):
        eng = _engine()
        a = eng.add_assessment(
            merge_id="MR-001",
            risk_factor=RiskFactor.REVIEWER_FAMILIARITY,
            value=75.0,
            threshold=80.0,
            breached=False,
            description="Reviewer has context",
        )
        assert a.merge_id == "MR-001"
        assert a.risk_factor == RiskFactor.REVIEWER_FAMILIARITY
        assert a.value == 75.0
        assert a.threshold == 80.0
        assert a.breached is False
        assert a.description == "Reviewer has context"

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_assessment(merge_id=f"MR-{i}")
        assert len(eng._assessments) == 2


# ---------------------------------------------------------------------------
# analyze_merge_risk_patterns
# ---------------------------------------------------------------------------


class TestAnalyzeMergeRiskPatterns:
    def test_with_data(self):
        eng = _engine()
        eng.record_merge(
            merge_id="MR-001",
            risk_factor=RiskFactor.CHANGE_SIZE,
            risk_score=70.0,
        )
        eng.record_merge(
            merge_id="MR-002",
            risk_factor=RiskFactor.CHANGE_SIZE,
            risk_score=90.0,
        )
        result = eng.analyze_merge_risk_patterns()
        assert "change_size" in result
        assert result["change_size"]["count"] == 2
        assert result["change_size"]["avg_risk_score"] == 80.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_merge_risk_patterns() == {}


# ---------------------------------------------------------------------------
# identify_high_risk_merges
# ---------------------------------------------------------------------------


class TestIdentifyHighRiskMerges:
    def test_detects_high_risk(self):
        eng = _engine()
        eng.record_merge(
            merge_id="MR-001",
            risk_level=RiskLevel.CRITICAL,
        )
        eng.record_merge(
            merge_id="MR-002",
            risk_level=RiskLevel.LOW,
        )
        results = eng.identify_high_risk_merges()
        assert len(results) == 1
        assert results[0]["merge_id"] == "MR-001"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_high_risk_merges() == []


# ---------------------------------------------------------------------------
# rank_by_risk_score
# ---------------------------------------------------------------------------


class TestRankByRiskScore:
    def test_ranked_descending(self):
        eng = _engine()
        eng.record_merge(merge_id="MR-001", service="api", risk_score=90.0)
        eng.record_merge(merge_id="MR-002", service="api", risk_score=80.0)
        eng.record_merge(merge_id="MR-003", service="web", risk_score=50.0)
        results = eng.rank_by_risk_score()
        assert len(results) == 2
        assert results[0]["service"] == "api"
        assert results[0]["avg_risk_score"] == 85.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_risk_score() == []


# ---------------------------------------------------------------------------
# detect_risk_trends
# ---------------------------------------------------------------------------


class TestDetectRiskTrends:
    def test_stable(self):
        eng = _engine()
        for val in [10.0, 10.0, 10.0, 10.0]:
            eng.add_assessment(merge_id="MR-001", value=val)
        result = eng.detect_risk_trends()
        assert result["trend"] == "stable"

    def test_increasing(self):
        eng = _engine()
        for val in [5.0, 5.0, 20.0, 20.0]:
            eng.add_assessment(merge_id="MR-001", value=val)
        result = eng.detect_risk_trends()
        assert result["trend"] == "increasing"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_risk_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_merge(
            merge_id="MR-001",
            risk_factor=RiskFactor.CHANGE_SIZE,
            risk_level=RiskLevel.CRITICAL,
            risk_score=50.0,
            service="api",
            team="sre",
        )
        report = eng.generate_report()
        assert isinstance(report, MergeRiskReport)
        assert report.total_records == 1
        assert report.high_risk_merges == 1
        assert report.avg_risk_score == 50.0
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
        eng.record_merge(merge_id="MR-001")
        eng.add_assessment(merge_id="MR-001")
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
        assert stats["factor_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_merge(
            merge_id="MR-001",
            risk_factor=RiskFactor.FILE_COMPLEXITY,
            service="api",
            team="sre",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_services"] == 1
        assert stats["unique_merges"] == 1
        assert "file_complexity" in stats["factor_distribution"]
