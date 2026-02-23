"""Tests for shieldops.observability.health_report — ServiceHealthReportGenerator."""

from __future__ import annotations

import time

import pytest

from shieldops.observability.health_report import (
    HealthGrade,
    HealthMetric,
    HealthReport,
    ReportStatus,
    ServiceHealthReportGenerator,
)


def _generator(**kw) -> ServiceHealthReportGenerator:
    return ServiceHealthReportGenerator(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    # HealthGrade (5 values)

    def test_health_grade_a(self):
        assert HealthGrade.A == "A"

    def test_health_grade_b(self):
        assert HealthGrade.B == "B"

    def test_health_grade_c(self):
        assert HealthGrade.C == "C"

    def test_health_grade_d(self):
        assert HealthGrade.D == "D"

    def test_health_grade_f(self):
        assert HealthGrade.F == "F"

    # ReportStatus (3 values)

    def test_report_status_draft(self):
        assert ReportStatus.DRAFT == "draft"

    def test_report_status_published(self):
        assert ReportStatus.PUBLISHED == "published"

    def test_report_status_archived(self):
        assert ReportStatus.ARCHIVED == "archived"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_health_metric_defaults(self):
        m = HealthMetric(name="uptime")
        assert m.name == "uptime"
        assert m.value == 0.0
        assert m.weight == 1.0
        assert m.grade == HealthGrade.C

    def test_health_report_defaults(self):
        r = HealthReport(service="web")
        assert r.id
        assert r.service == "web"
        assert r.metrics == []
        assert r.overall_grade == HealthGrade.C
        assert r.overall_score == 0.0
        assert r.status == ReportStatus.DRAFT
        assert r.recommendations == []
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# create_report
# ---------------------------------------------------------------------------


class TestCreateReport:
    def test_creates_draft_report(self):
        gen = _generator()
        now = time.time()
        r = gen.create_report("web", now - 3600, now)
        assert r.service == "web"
        assert r.status == ReportStatus.DRAFT
        assert r.period_start == now - 3600
        assert r.period_end == now

    def test_report_stored(self):
        gen = _generator()
        now = time.time()
        r = gen.create_report("web", now - 3600, now)
        assert gen.get_report(r.id) is not None

    def test_evicts_at_max_reports(self):
        gen = _generator(max_reports=2)
        now = time.time()
        r1 = gen.create_report("svc1", now, now + 1)
        gen.create_report("svc2", now, now + 1)
        gen.create_report("svc3", now, now + 1)
        reports = gen.list_reports()
        assert len(reports) == 2
        ids = {r.id for r in reports}
        assert r1.id not in ids


# ---------------------------------------------------------------------------
# add_metric
# ---------------------------------------------------------------------------


class TestAddMetric:
    def test_adds_metric_with_auto_grade_a(self):
        gen = _generator()
        r = gen.create_report("web", 0.0, 1.0)
        updated = gen.add_metric(r.id, "uptime", 95.0)
        assert updated is not None
        assert len(updated.metrics) == 1
        assert updated.metrics[0].grade == HealthGrade.A

    def test_auto_grade_b(self):
        gen = _generator()
        r = gen.create_report("web", 0.0, 1.0)
        updated = gen.add_metric(r.id, "uptime", 85.0)
        assert updated.metrics[0].grade == HealthGrade.B

    def test_auto_grade_c(self):
        gen = _generator()
        r = gen.create_report("web", 0.0, 1.0)
        updated = gen.add_metric(r.id, "uptime", 75.0)
        assert updated.metrics[0].grade == HealthGrade.C

    def test_auto_grade_d(self):
        gen = _generator()
        r = gen.create_report("web", 0.0, 1.0)
        updated = gen.add_metric(r.id, "uptime", 65.0)
        assert updated.metrics[0].grade == HealthGrade.D

    def test_auto_grade_f(self):
        gen = _generator()
        r = gen.create_report("web", 0.0, 1.0)
        updated = gen.add_metric(r.id, "uptime", 50.0)
        assert updated.metrics[0].grade == HealthGrade.F

    def test_returns_none_for_unknown_report(self):
        gen = _generator()
        assert gen.add_metric("nonexistent", "m", 1.0) is None

    def test_metric_weight_is_stored(self):
        gen = _generator()
        r = gen.create_report("web", 0.0, 1.0)
        gen.add_metric(r.id, "latency", 80.0, weight=2.0)
        assert r.metrics[0].weight == 2.0


# ---------------------------------------------------------------------------
# add_recommendation
# ---------------------------------------------------------------------------


class TestAddRecommendation:
    def test_appends_recommendation(self):
        gen = _generator()
        r = gen.create_report("web", 0.0, 1.0)
        updated = gen.add_recommendation(r.id, "Increase replicas")
        assert updated is not None
        assert "Increase replicas" in updated.recommendations

    def test_returns_none_for_unknown(self):
        gen = _generator()
        assert gen.add_recommendation("nope", "text") is None

    def test_multiple_recommendations(self):
        gen = _generator()
        r = gen.create_report("web", 0.0, 1.0)
        gen.add_recommendation(r.id, "First")
        gen.add_recommendation(r.id, "Second")
        assert len(r.recommendations) == 2


# ---------------------------------------------------------------------------
# publish_report
# ---------------------------------------------------------------------------


class TestPublishReport:
    def test_sets_status_to_published(self):
        gen = _generator()
        r = gen.create_report("web", 0.0, 1.0)
        updated = gen.publish_report(r.id)
        assert updated is not None
        assert updated.status == ReportStatus.PUBLISHED

    def test_returns_none_for_unknown(self):
        gen = _generator()
        assert gen.publish_report("nope") is None


# ---------------------------------------------------------------------------
# archive_report
# ---------------------------------------------------------------------------


class TestArchiveReport:
    def test_sets_status_to_archived(self):
        gen = _generator()
        r = gen.create_report("web", 0.0, 1.0)
        updated = gen.archive_report(r.id)
        assert updated is not None
        assert updated.status == ReportStatus.ARCHIVED

    def test_returns_none_for_unknown(self):
        gen = _generator()
        assert gen.archive_report("nope") is None


# ---------------------------------------------------------------------------
# calculate_overall
# ---------------------------------------------------------------------------


class TestCalculateOverall:
    def test_weighted_average_of_metrics(self):
        gen = _generator()
        r = gen.create_report("web", 0.0, 1.0)
        gen.add_metric(r.id, "uptime", 90.0, weight=2.0)
        gen.add_metric(r.id, "latency", 80.0, weight=1.0)
        updated = gen.calculate_overall(r.id)
        assert updated is not None
        # (90*2 + 80*1) / 3 = 260/3 = 86.67
        assert updated.overall_score == pytest.approx(86.67, abs=0.01)
        assert updated.overall_grade == HealthGrade.B

    def test_empty_metrics_returns_f_and_zero(self):
        gen = _generator()
        r = gen.create_report("web", 0.0, 1.0)
        updated = gen.calculate_overall(r.id)
        assert updated is not None
        assert updated.overall_score == 0.0
        assert updated.overall_grade == HealthGrade.F

    def test_zero_total_weight_returns_f(self):
        gen = _generator()
        r = gen.create_report("web", 0.0, 1.0)
        gen.add_metric(r.id, "m1", 90.0, weight=0.0)
        updated = gen.calculate_overall(r.id)
        assert updated.overall_score == 0.0
        assert updated.overall_grade == HealthGrade.F

    def test_returns_none_for_unknown(self):
        gen = _generator()
        assert gen.calculate_overall("nope") is None


# ---------------------------------------------------------------------------
# get_report
# ---------------------------------------------------------------------------


class TestGetReport:
    def test_found(self):
        gen = _generator()
        r = gen.create_report("web", 0.0, 1.0)
        assert gen.get_report(r.id) is not None
        assert gen.get_report(r.id).service == "web"

    def test_not_found_returns_none(self):
        gen = _generator()
        assert gen.get_report("nonexistent") is None


# ---------------------------------------------------------------------------
# list_reports
# ---------------------------------------------------------------------------


class TestListReports:
    def test_filter_by_service(self):
        gen = _generator()
        gen.create_report("web", 0.0, 1.0)
        gen.create_report("api", 0.0, 1.0)
        results = gen.list_reports(service="web")
        assert len(results) == 1
        assert results[0].service == "web"

    def test_filter_by_status(self):
        gen = _generator()
        r1 = gen.create_report("web", 0.0, 1.0)
        gen.create_report("api", 0.0, 1.0)
        gen.publish_report(r1.id)
        results = gen.list_reports(status=ReportStatus.PUBLISHED)
        assert len(results) == 1
        assert results[0].status == ReportStatus.PUBLISHED

    def test_filter_by_string_status(self):
        gen = _generator()
        gen.create_report("web", 0.0, 1.0)
        results = gen.list_reports(status="draft")
        assert len(results) == 1


# ---------------------------------------------------------------------------
# get_latest_report
# ---------------------------------------------------------------------------


class TestGetLatestReport:
    def test_returns_most_recent_for_service(self):
        gen = _generator()
        gen.create_report("web", 0.0, 1.0)
        r2 = gen.create_report("web", 1.0, 2.0)
        latest = gen.get_latest_report("web")
        assert latest is not None
        assert latest.id == r2.id

    def test_none_if_no_reports(self):
        gen = _generator()
        assert gen.get_latest_report("web") is None

    def test_ignores_other_services(self):
        gen = _generator()
        gen.create_report("api", 0.0, 1.0)
        assert gen.get_latest_report("web") is None


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_empty_stats(self):
        gen = _generator()
        stats = gen.get_stats()
        assert stats["total_reports"] == 0
        assert stats["services_covered"] == 0
        assert stats["status_distribution"] == {}
        assert stats["grade_distribution"] == {}

    def test_populated_stats(self):
        gen = _generator()
        r1 = gen.create_report("web", 0.0, 1.0)
        gen.create_report("api", 0.0, 1.0)
        gen.publish_report(r1.id)
        stats = gen.get_stats()
        assert stats["total_reports"] == 2
        assert stats["services_covered"] == 2
        status_dist = stats["status_distribution"]
        assert status_dist[ReportStatus.PUBLISHED] == 1
        assert status_dist[ReportStatus.DRAFT] == 1
        grade_dist = stats["grade_distribution"]
        # Both reports have default overall_grade=C
        assert grade_dist[HealthGrade.C] == 2
