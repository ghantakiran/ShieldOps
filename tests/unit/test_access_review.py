"""Tests for shieldops.audit.access_review — AccessReviewTracker."""

from __future__ import annotations

from shieldops.audit.access_review import (
    AccessReviewRecord,
    AccessReviewReport,
    AccessReviewTracker,
    AccessRisk,
    ReviewFinding,
    ReviewStatus,
    ReviewType,
)


def _engine(**kw) -> AccessReviewTracker:
    return AccessReviewTracker(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_type_quarterly(self):
        assert ReviewType.QUARTERLY == "quarterly"

    def test_type_semi_annual(self):
        assert ReviewType.SEMI_ANNUAL == "semi_annual"

    def test_type_annual(self):
        assert ReviewType.ANNUAL == "annual"

    def test_type_ad_hoc(self):
        assert ReviewType.AD_HOC == "ad_hoc"

    def test_type_continuous(self):
        assert ReviewType.CONTINUOUS == "continuous"

    def test_status_completed(self):
        assert ReviewStatus.COMPLETED == "completed"

    def test_status_in_progress(self):
        assert ReviewStatus.IN_PROGRESS == "in_progress"

    def test_status_overdue(self):
        assert ReviewStatus.OVERDUE == "overdue"

    def test_status_not_started(self):
        assert ReviewStatus.NOT_STARTED == "not_started"

    def test_status_cancelled(self):
        assert ReviewStatus.CANCELLED == "cancelled"

    def test_risk_critical(self):
        assert AccessRisk.CRITICAL == "critical"

    def test_risk_high(self):
        assert AccessRisk.HIGH == "high"

    def test_risk_moderate(self):
        assert AccessRisk.MODERATE == "moderate"

    def test_risk_low(self):
        assert AccessRisk.LOW == "low"

    def test_risk_minimal(self):
        assert AccessRisk.MINIMAL == "minimal"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_access_review_record_defaults(self):
        r = AccessReviewRecord()
        assert r.id
        assert r.review_id == ""
        assert r.review_type == ReviewType.QUARTERLY
        assert r.review_status == ReviewStatus.NOT_STARTED
        assert r.access_risk == AccessRisk.MINIMAL
        assert r.completion_pct == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_review_finding_defaults(self):
        f = ReviewFinding()
        assert f.id
        assert f.review_id == ""
        assert f.review_type == ReviewType.QUARTERLY
        assert f.finding_score == 0.0
        assert f.threshold == 0.0
        assert f.breached is False
        assert f.description == ""
        assert f.created_at > 0

    def test_report_defaults(self):
        r = AccessReviewReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_findings == 0
        assert r.overdue_reviews == 0
        assert r.avg_completion_pct == 0.0
        assert r.by_review_type == {}
        assert r.by_status == {}
        assert r.by_risk == {}
        assert r.top_overdue == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_review
# ---------------------------------------------------------------------------


class TestRecordReview:
    def test_basic(self):
        eng = _engine()
        r = eng.record_review(
            review_id="REV-001",
            review_type=ReviewType.QUARTERLY,
            review_status=ReviewStatus.COMPLETED,
            access_risk=AccessRisk.HIGH,
            completion_pct=100.0,
            service="api-gateway",
            team="security",
        )
        assert r.review_id == "REV-001"
        assert r.review_type == ReviewType.QUARTERLY
        assert r.review_status == ReviewStatus.COMPLETED
        assert r.access_risk == AccessRisk.HIGH
        assert r.completion_pct == 100.0
        assert r.service == "api-gateway"
        assert r.team == "security"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_review(review_id=f"REV-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_review
# ---------------------------------------------------------------------------


class TestGetReview:
    def test_found(self):
        eng = _engine()
        r = eng.record_review(
            review_id="REV-001",
            completion_pct=100.0,
        )
        result = eng.get_review(r.id)
        assert result is not None
        assert result.completion_pct == 100.0

    def test_not_found(self):
        eng = _engine()
        assert eng.get_review("nonexistent") is None


# ---------------------------------------------------------------------------
# list_reviews
# ---------------------------------------------------------------------------


class TestListReviews:
    def test_list_all(self):
        eng = _engine()
        eng.record_review(review_id="REV-001")
        eng.record_review(review_id="REV-002")
        assert len(eng.list_reviews()) == 2

    def test_filter_by_review_type(self):
        eng = _engine()
        eng.record_review(
            review_id="REV-001",
            review_type=ReviewType.QUARTERLY,
        )
        eng.record_review(
            review_id="REV-002",
            review_type=ReviewType.ANNUAL,
        )
        results = eng.list_reviews(review_type=ReviewType.QUARTERLY)
        assert len(results) == 1

    def test_filter_by_status(self):
        eng = _engine()
        eng.record_review(
            review_id="REV-001",
            review_status=ReviewStatus.COMPLETED,
        )
        eng.record_review(
            review_id="REV-002",
            review_status=ReviewStatus.OVERDUE,
        )
        results = eng.list_reviews(status=ReviewStatus.COMPLETED)
        assert len(results) == 1

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_review(review_id="REV-001", service="api-gateway")
        eng.record_review(review_id="REV-002", service="auth-svc")
        results = eng.list_reviews(service="api-gateway")
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_review(review_id="REV-001", team="security")
        eng.record_review(review_id="REV-002", team="platform")
        results = eng.list_reviews(team="security")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_review(review_id=f"REV-{i}")
        assert len(eng.list_reviews(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_finding
# ---------------------------------------------------------------------------


class TestAddFinding:
    def test_basic(self):
        eng = _engine()
        f = eng.add_finding(
            review_id="REV-001",
            review_type=ReviewType.QUARTERLY,
            finding_score=75.0,
            threshold=80.0,
            breached=True,
            description="Stale admin permissions detected",
        )
        assert f.review_id == "REV-001"
        assert f.review_type == ReviewType.QUARTERLY
        assert f.finding_score == 75.0
        assert f.threshold == 80.0
        assert f.breached is True
        assert f.description == "Stale admin permissions detected"

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_finding(review_id=f"REV-{i}")
        assert len(eng._findings) == 2


# ---------------------------------------------------------------------------
# analyze_review_compliance
# ---------------------------------------------------------------------------


class TestAnalyzeReviewCompliance:
    def test_with_data(self):
        eng = _engine()
        eng.record_review(
            review_id="REV-001",
            review_type=ReviewType.QUARTERLY,
            completion_pct=80.0,
        )
        eng.record_review(
            review_id="REV-002",
            review_type=ReviewType.QUARTERLY,
            completion_pct=60.0,
        )
        result = eng.analyze_review_compliance()
        assert "quarterly" in result
        assert result["quarterly"]["count"] == 2
        assert result["quarterly"]["avg_completion"] == 70.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_review_compliance() == {}


# ---------------------------------------------------------------------------
# identify_overdue_reviews
# ---------------------------------------------------------------------------


class TestIdentifyOverdueReviews:
    def test_detects_overdue(self):
        eng = _engine()
        eng.record_review(
            review_id="REV-001",
            review_status=ReviewStatus.OVERDUE,
        )
        eng.record_review(
            review_id="REV-002",
            review_status=ReviewStatus.COMPLETED,
        )
        results = eng.identify_overdue_reviews()
        assert len(results) == 1
        assert results[0]["review_id"] == "REV-001"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_overdue_reviews() == []


# ---------------------------------------------------------------------------
# rank_by_completion
# ---------------------------------------------------------------------------


class TestRankByCompletion:
    def test_ranked_ascending(self):
        eng = _engine()
        eng.record_review(
            review_id="REV-001",
            service="api-gateway",
            completion_pct=90.0,
        )
        eng.record_review(
            review_id="REV-002",
            service="auth-svc",
            completion_pct=60.0,
        )
        results = eng.rank_by_completion()
        assert len(results) == 2
        assert results[0]["service"] == "auth-svc"
        assert results[0]["avg_completion"] == 60.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_completion() == []


# ---------------------------------------------------------------------------
# detect_review_trends
# ---------------------------------------------------------------------------


class TestDetectReviewTrends:
    def test_stable(self):
        eng = _engine()
        for score in [50.0, 50.0, 50.0, 50.0]:
            eng.add_finding(review_id="REV-001", finding_score=score)
        result = eng.detect_review_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        for score in [30.0, 30.0, 80.0, 80.0]:
            eng.add_finding(review_id="REV-001", finding_score=score)
        result = eng.detect_review_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_review_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_review(
            review_id="REV-001",
            review_type=ReviewType.QUARTERLY,
            review_status=ReviewStatus.OVERDUE,
            completion_pct=30.0,
            service="api-gateway",
        )
        report = eng.generate_report()
        assert isinstance(report, AccessReviewReport)
        assert report.total_records == 1
        assert report.overdue_reviews == 1
        assert len(report.top_overdue) == 1
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
        eng.record_review(review_id="REV-001")
        eng.add_finding(review_id="REV-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._findings) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_findings"] == 0
        assert stats["type_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_review(
            review_id="REV-001",
            review_type=ReviewType.QUARTERLY,
            service="api-gateway",
            team="security",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "quarterly" in stats["type_distribution"]
