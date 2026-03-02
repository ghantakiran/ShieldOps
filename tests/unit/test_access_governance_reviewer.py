"""Tests for shieldops.audit.access_governance_reviewer — AccessGovernanceReviewer."""

from __future__ import annotations

from shieldops.audit.access_governance_reviewer import (
    AccessGovernanceReport,
    AccessGovernanceReviewer,
    AccessRisk,
    ReviewAnalysis,
    ReviewOutcome,
    ReviewRecord,
    ReviewType,
)


def _engine(**kw) -> AccessGovernanceReviewer:
    return AccessGovernanceReviewer(**kw)


class TestEnums:
    def test_type_periodic(self):
        assert ReviewType.PERIODIC == "periodic"

    def test_type_triggered(self):
        assert ReviewType.TRIGGERED == "triggered"

    def test_type_certification(self):
        assert ReviewType.CERTIFICATION == "certification"

    def test_type_privileged_access(self):
        assert ReviewType.PRIVILEGED_ACCESS == "privileged_access"

    def test_type_service_account(self):
        assert ReviewType.SERVICE_ACCOUNT == "service_account"

    def test_outcome_approved(self):
        assert ReviewOutcome.APPROVED == "approved"

    def test_outcome_revoked(self):
        assert ReviewOutcome.REVOKED == "revoked"

    def test_outcome_modified(self):
        assert ReviewOutcome.MODIFIED == "modified"

    def test_outcome_escalated(self):
        assert ReviewOutcome.ESCALATED == "escalated"

    def test_outcome_deferred(self):
        assert ReviewOutcome.DEFERRED == "deferred"

    def test_risk_high(self):
        assert AccessRisk.HIGH == "high"

    def test_risk_medium(self):
        assert AccessRisk.MEDIUM == "medium"

    def test_risk_low(self):
        assert AccessRisk.LOW == "low"

    def test_risk_minimal(self):
        assert AccessRisk.MINIMAL == "minimal"

    def test_risk_none(self):
        assert AccessRisk.NONE == "none"


class TestModels:
    def test_record_defaults(self):
        r = ReviewRecord()
        assert r.id
        assert r.review_name == ""
        assert r.review_type == ReviewType.PERIODIC
        assert r.review_outcome == ReviewOutcome.APPROVED
        assert r.access_risk == AccessRisk.HIGH
        assert r.review_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_analysis_defaults(self):
        a = ReviewAnalysis()
        assert a.id
        assert a.review_name == ""
        assert a.review_type == ReviewType.PERIODIC
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = AccessGovernanceReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_review_score == 0.0
        assert r.by_type == {}
        assert r.by_outcome == {}
        assert r.by_risk == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_review(
            review_name="quarterly-access-review",
            review_type=ReviewType.PERIODIC,
            review_outcome=ReviewOutcome.MODIFIED,
            access_risk=AccessRisk.HIGH,
            review_score=85.0,
            service="iam-svc",
            team="security",
        )
        assert r.review_name == "quarterly-access-review"
        assert r.review_type == ReviewType.PERIODIC
        assert r.review_score == 85.0
        assert r.service == "iam-svc"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_review(review_name=f"rev-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_review(review_name="test")
        assert eng.get_record(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_record("nonexistent") is None


class TestList:
    def test_list_all(self):
        eng = _engine()
        eng.record_review(review_name="a")
        eng.record_review(review_name="b")
        assert len(eng.list_records()) == 2

    def test_filter_by_review_type(self):
        eng = _engine()
        eng.record_review(review_name="a", review_type=ReviewType.PERIODIC)
        eng.record_review(review_name="b", review_type=ReviewType.TRIGGERED)
        assert len(eng.list_records(review_type=ReviewType.PERIODIC)) == 1

    def test_filter_by_review_outcome(self):
        eng = _engine()
        eng.record_review(review_name="a", review_outcome=ReviewOutcome.APPROVED)
        eng.record_review(review_name="b", review_outcome=ReviewOutcome.REVOKED)
        assert len(eng.list_records(review_outcome=ReviewOutcome.APPROVED)) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_review(review_name="a", team="sec")
        eng.record_review(review_name="b", team="ops")
        assert len(eng.list_records(team="sec")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_review(review_name=f"r-{i}")
        assert len(eng.list_records(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            review_name="test",
            analysis_score=88.5,
            breached=True,
            description="access risk",
        )
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(review_name=f"t-{i}")
        assert len(eng._analyses) == 2


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_review(review_name="a", review_type=ReviewType.PERIODIC, review_score=90.0)
        eng.record_review(review_name="b", review_type=ReviewType.PERIODIC, review_score=70.0)
        result = eng.analyze_distribution()
        assert "periodic" in result
        assert result["periodic"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(threshold=80.0)
        eng.record_review(review_name="a", review_score=60.0)
        eng.record_review(review_name="b", review_score=90.0)
        assert len(eng.identify_gaps()) == 1

    def test_sorted_ascending(self):
        eng = _engine(threshold=80.0)
        eng.record_review(review_name="a", review_score=50.0)
        eng.record_review(review_name="b", review_score=30.0)
        results = eng.identify_gaps()
        assert results[0]["review_score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_gaps() == []


class TestRankByScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_review(review_name="a", service="auth", review_score=90.0)
        eng.record_review(review_name="b", service="api", review_score=50.0)
        results = eng.rank_by_score()
        assert results[0]["service"] == "api"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_score() == []


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(review_name="t", analysis_score=50.0)
        assert eng.detect_trends()["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(review_name="a", analysis_score=20.0)
        eng.add_analysis(review_name="b", analysis_score=20.0)
        eng.add_analysis(review_name="c", analysis_score=80.0)
        eng.add_analysis(review_name="d", analysis_score=80.0)
        assert eng.detect_trends()["trend"] == "improving"

    def test_insufficient_data(self):
        eng = _engine()
        assert eng.detect_trends()["trend"] == "insufficient_data"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(threshold=80.0)
        eng.record_review(review_name="test", review_score=50.0)
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
        eng.record_review(review_name="test")
        eng.add_analysis(review_name="test")
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
        eng.record_review(review_name="test", service="auth", team="sec")
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
