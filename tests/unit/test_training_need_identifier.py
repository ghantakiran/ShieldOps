"""Tests for shieldops.operations.training_need_identifier."""

from __future__ import annotations

from shieldops.operations.training_need_identifier import (
    DeliveryMethod,
    NeedUrgency,
    TrainingAnalysis,
    TrainingDomain,
    TrainingNeedIdentifier,
    TrainingRecord,
    TrainingReport,
)


def _engine(**kw) -> TrainingNeedIdentifier:
    return TrainingNeedIdentifier(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_domain_security(self):
        assert TrainingDomain.SECURITY == "security"

    def test_domain_cloud(self):
        assert TrainingDomain.CLOUD == "cloud"

    def test_domain_kubernetes(self):
        assert TrainingDomain.KUBERNETES == "kubernetes"

    def test_domain_observability(self):
        assert TrainingDomain.OBSERVABILITY == "observability"

    def test_domain_incident_mgmt(self):
        assert TrainingDomain.INCIDENT_MGMT == "incident_mgmt"

    def test_urgency_immediate(self):
        assert NeedUrgency.IMMEDIATE == "immediate"

    def test_urgency_high(self):
        assert NeedUrgency.HIGH == "high"

    def test_urgency_medium(self):
        assert NeedUrgency.MEDIUM == "medium"

    def test_urgency_low(self):
        assert NeedUrgency.LOW == "low"

    def test_urgency_optional(self):
        assert NeedUrgency.OPTIONAL == "optional"

    def test_method_self_paced(self):
        assert DeliveryMethod.SELF_PACED == "self_paced"

    def test_method_instructor_led(self):
        assert DeliveryMethod.INSTRUCTOR_LED == "instructor_led"

    def test_method_mentoring(self):
        assert DeliveryMethod.MENTORING == "mentoring"

    def test_method_workshop(self):
        assert DeliveryMethod.WORKSHOP == "workshop"

    def test_method_certification(self):
        assert DeliveryMethod.CERTIFICATION == "certification"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_training_record_defaults(self):
        r = TrainingRecord()
        assert r.id
        assert r.engineer == ""
        assert r.team == ""
        assert r.training_domain == TrainingDomain.CLOUD
        assert r.need_urgency == NeedUrgency.MEDIUM
        assert r.delivery_method == DeliveryMethod.SELF_PACED
        assert r.need_score == 0.0
        assert r.estimated_hours == 0.0
        assert r.created_at > 0

    def test_training_analysis_defaults(self):
        a = TrainingAnalysis()
        assert a.id
        assert a.engineer == ""
        assert a.analysis_score == 0.0
        assert a.breached is False
        assert a.created_at > 0

    def test_training_report_defaults(self):
        r = TrainingReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_need_score == 0.0
        assert r.by_domain == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_training / get_training
# ---------------------------------------------------------------------------


class TestRecordAndGet:
    def test_basic(self):
        eng = _engine()
        r = eng.record_training(
            engineer="alice",
            team="sre",
            training_domain=TrainingDomain.KUBERNETES,
            need_urgency=NeedUrgency.IMMEDIATE,
            delivery_method=DeliveryMethod.WORKSHOP,
            need_score=85.0,
            estimated_hours=16.0,
        )
        assert r.engineer == "alice"
        assert r.training_domain == TrainingDomain.KUBERNETES
        assert r.need_score == 85.0
        assert r.estimated_hours == 16.0

    def test_get_found(self):
        eng = _engine()
        r = eng.record_training(engineer="bob", need_score=65.0)
        found = eng.get_training(r.id)
        assert found is not None
        assert found.need_score == 65.0

    def test_get_not_found(self):
        eng = _engine()
        assert eng.get_training("nonexistent") is None

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_training(engineer=f"eng-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# list_trainings
# ---------------------------------------------------------------------------


class TestListAndFilter:
    def test_list_all(self):
        eng = _engine()
        eng.record_training(engineer="alice")
        eng.record_training(engineer="bob")
        assert len(eng.list_trainings()) == 2

    def test_filter_by_domain(self):
        eng = _engine()
        eng.record_training(engineer="alice", training_domain=TrainingDomain.SECURITY)
        eng.record_training(engineer="bob", training_domain=TrainingDomain.CLOUD)
        results = eng.list_trainings(training_domain=TrainingDomain.SECURITY)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_training(engineer="alice", team="sre")
        eng.record_training(engineer="bob", team="platform")
        results = eng.list_trainings(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_training(engineer=f"eng-{i}")
        assert len(eng.list_trainings(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            engineer="alice",
            training_domain=TrainingDomain.SECURITY,
            analysis_score=80.0,
            threshold=50.0,
            breached=True,
            description="security training needed",
        )
        assert a.engineer == "alice"
        assert a.analysis_score == 80.0
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(engineer=f"eng-{i}")
        assert len(eng._analyses) == 2

    def test_defaults(self):
        eng = _engine()
        a = eng.add_analysis(engineer="alice")
        assert a.analysis_score == 0.0
        assert a.breached is False


# ---------------------------------------------------------------------------
# analyze_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_training(
            engineer="alice",
            training_domain=TrainingDomain.KUBERNETES,
            need_score=80.0,
        )
        eng.record_training(
            engineer="bob",
            training_domain=TrainingDomain.KUBERNETES,
            need_score=60.0,
        )
        result = eng.analyze_distribution()
        assert "kubernetes" in result
        assert result["kubernetes"]["count"] == 2
        assert result["kubernetes"]["avg_need_score"] == 70.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


# ---------------------------------------------------------------------------
# identify_training_gaps
# ---------------------------------------------------------------------------


class TestIdentifyGaps:
    def test_detects_above_threshold(self):
        eng = _engine(threshold=60.0)
        eng.record_training(engineer="alice", need_score=80.0)
        eng.record_training(engineer="bob", need_score=40.0)
        results = eng.identify_training_gaps()
        assert len(results) == 1
        assert results[0]["engineer"] == "alice"

    def test_sorted_descending(self):
        eng = _engine(threshold=50.0)
        eng.record_training(engineer="alice", need_score=90.0)
        eng.record_training(engineer="bob", need_score=70.0)
        results = eng.identify_training_gaps()
        assert results[0]["need_score"] == 90.0


# ---------------------------------------------------------------------------
# rank_by_need
# ---------------------------------------------------------------------------


class TestRankBy:
    def test_sorted_descending(self):
        eng = _engine()
        eng.record_training(engineer="alice", need_score=30.0)
        eng.record_training(engineer="bob", need_score=80.0)
        results = eng.rank_by_need()
        assert results[0]["engineer"] == "bob"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_need() == []


# ---------------------------------------------------------------------------
# detect_training_trends
# ---------------------------------------------------------------------------


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(engineer="alice", analysis_score=50.0)
        result = eng.detect_training_trends()
        assert result["trend"] == "stable"

    def test_worsening(self):
        eng = _engine()
        eng.add_analysis(engineer="a", analysis_score=20.0)
        eng.add_analysis(engineer="b", analysis_score=20.0)
        eng.add_analysis(engineer="c", analysis_score=80.0)
        eng.add_analysis(engineer="d", analysis_score=80.0)
        result = eng.detect_training_trends()
        assert result["trend"] == "worsening"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_training_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestReport:
    def test_populated(self):
        eng = _engine(threshold=60.0)
        eng.record_training(
            engineer="alice",
            training_domain=TrainingDomain.SECURITY,
            need_urgency=NeedUrgency.IMMEDIATE,
            need_score=80.0,
        )
        report = eng.generate_report()
        assert isinstance(report, TrainingReport)
        assert report.total_records == 1
        assert report.gap_count == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "healthy" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearAndStats:
    def test_clears(self):
        eng = _engine()
        eng.record_training(engineer="alice")
        eng.add_analysis(engineer="alice")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0

    def test_get_stats(self):
        eng = _engine()
        eng.record_training(engineer="alice", team="sre", training_domain=TrainingDomain.KUBERNETES)
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert "kubernetes" in stats["domain_distribution"]
        assert stats["unique_engineers"] == 1


# ---------------------------------------------------------------------------
# Eviction
# ---------------------------------------------------------------------------


class TestEviction:
    def test_analyses_eviction(self):
        eng = _engine(max_records=2)
        for i in range(6):
            eng.add_analysis(engineer=f"eng-{i}", analysis_score=float(i))
        assert len(eng._analyses) == 2
        assert eng._analyses[-1].analysis_score == 5.0
