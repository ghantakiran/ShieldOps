"""Tests for FailurePredictionIntelligence."""

from __future__ import annotations

from shieldops.operations.failure_prediction_intelligence import (
    FailureLikelihood,
    FailurePredictionIntelligence,
    FailurePredictionIntelligenceAnalysis,
    FailurePredictionIntelligenceRecord,
    FailurePredictionIntelligenceReport,
    FailureType,
    MitigationStrategy,
)


def _engine(**kw) -> FailurePredictionIntelligence:
    return FailurePredictionIntelligence(**kw)


class TestEnums:
    def test_failure_type_first(self):
        assert FailureType.HARDWARE == "hardware"

    def test_failure_type_second(self):
        assert FailureType.SOFTWARE == "software"

    def test_failure_type_third(self):
        assert FailureType.NETWORK == "network"

    def test_failure_type_fourth(self):
        assert FailureType.CAPACITY == "capacity"

    def test_failure_type_fifth(self):
        assert FailureType.DEPENDENCY == "dependency"

    def test_failure_likelihood_first(self):
        assert FailureLikelihood.IMMINENT == "imminent"

    def test_failure_likelihood_second(self):
        assert FailureLikelihood.LIKELY == "likely"

    def test_failure_likelihood_third(self):
        assert FailureLikelihood.POSSIBLE == "possible"

    def test_failure_likelihood_fourth(self):
        assert FailureLikelihood.UNLIKELY == "unlikely"

    def test_failure_likelihood_fifth(self):
        assert FailureLikelihood.RARE == "rare"

    def test_mitigation_strategy_first(self):
        assert MitigationStrategy.PREEMPTIVE == "preemptive"

    def test_mitigation_strategy_second(self):
        assert MitigationStrategy.REACTIVE == "reactive"

    def test_mitigation_strategy_third(self):
        assert MitigationStrategy.REDUNDANCY == "redundancy"

    def test_mitigation_strategy_fourth(self):
        assert MitigationStrategy.GRACEFUL_DEGRADATION == "graceful_degradation"

    def test_mitigation_strategy_fifth(self):
        assert MitigationStrategy.MANUAL == "manual"


class TestModels:
    def test_record_defaults(self):
        r = FailurePredictionIntelligenceRecord()
        assert r.id
        assert r.name == ""
        assert r.failure_type == FailureType.HARDWARE
        assert r.failure_likelihood == FailureLikelihood.IMMINENT
        assert r.mitigation_strategy == MitigationStrategy.PREEMPTIVE
        assert r.score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_analysis_defaults(self):
        a = FailurePredictionIntelligenceAnalysis()
        assert a.id
        assert a.name == ""
        assert a.failure_type == FailureType.HARDWARE
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = FailurePredictionIntelligenceReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_score == 0.0
        assert r.by_failure_type == {}
        assert r.by_failure_likelihood == {}
        assert r.by_mitigation_strategy == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_item(
            name="test-001",
            failure_type=FailureType.HARDWARE,
            failure_likelihood=FailureLikelihood.LIKELY,
            mitigation_strategy=MitigationStrategy.REDUNDANCY,
            score=85.0,
            service="svc-a",
            team="team-a",
        )
        assert r.name == "test-001"
        assert r.failure_type == FailureType.HARDWARE
        assert r.score == 85.0
        assert r.service == "svc-a"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_item(name=f"item-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_item(name="test")
        assert eng.get_record(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_record("nonexistent") is None


class TestList:
    def test_list_all(self):
        eng = _engine()
        eng.record_item(name="a")
        eng.record_item(name="b")
        assert len(eng.list_records()) == 2

    def test_filter_by_failure_type(self):
        eng = _engine()
        eng.record_item(name="a", failure_type=FailureType.SOFTWARE)
        eng.record_item(name="b", failure_type=FailureType.HARDWARE)
        assert len(eng.list_records(failure_type=FailureType.SOFTWARE)) == 1

    def test_filter_by_failure_likelihood(self):
        eng = _engine()
        eng.record_item(name="a", failure_likelihood=FailureLikelihood.IMMINENT)
        eng.record_item(name="b", failure_likelihood=FailureLikelihood.LIKELY)
        assert len(eng.list_records(failure_likelihood=FailureLikelihood.IMMINENT)) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_item(name="a", team="sec")
        eng.record_item(name="b", team="ops")
        assert len(eng.list_records(team="sec")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_item(name=f"a-{i}")
        assert len(eng.list_records(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            name="test",
            analysis_score=88.5,
            breached=True,
            description="test analysis",
        )
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(name=f"t-{i}")
        assert len(eng._analyses) == 2


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_item(name="a", failure_type=FailureType.SOFTWARE, score=90.0)
        eng.record_item(name="b", failure_type=FailureType.SOFTWARE, score=70.0)
        result = eng.analyze_distribution()
        assert "software" in result
        assert result["software"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(threshold=80.0)
        eng.record_item(name="a", score=60.0)
        eng.record_item(name="b", score=90.0)
        assert len(eng.identify_gaps()) == 1

    def test_sorted_ascending(self):
        eng = _engine(threshold=80.0)
        eng.record_item(name="a", score=50.0)
        eng.record_item(name="b", score=30.0)
        results = eng.identify_gaps()
        assert results[0]["score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_gaps() == []


class TestRankByScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_item(name="a", service="auth", score=90.0)
        eng.record_item(name="b", service="api", score=50.0)
        results = eng.rank_by_score()
        assert results[0]["service"] == "api"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_score() == []


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(name="t", analysis_score=50.0)
        assert eng.detect_trends()["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(name="a", analysis_score=20.0)
        eng.add_analysis(name="b", analysis_score=20.0)
        eng.add_analysis(name="c", analysis_score=80.0)
        eng.add_analysis(name="d", analysis_score=80.0)
        assert eng.detect_trends()["trend"] == "improving"

    def test_insufficient_data(self):
        eng = _engine()
        assert eng.detect_trends()["trend"] == "insufficient_data"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(threshold=80.0)
        eng.record_item(name="test", score=50.0)
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
        eng.record_item(name="test")
        eng.add_analysis(name="test")
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
        eng.record_item(name="test", service="auth", team="sec")
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
