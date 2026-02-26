"""Tests for shieldops.operations.runbook_recommender — RunbookRecommendationEngine."""

from __future__ import annotations

from shieldops.operations.runbook_recommender import (
    MatchCriteria,
    RecommendationConfidence,
    RecommendationRecord,
    RunbookMatch,
    RunbookRecommendationEngine,
    RunbookRecommenderReport,
    RunbookRelevance,
)


def _engine(**kw) -> RunbookRecommendationEngine:
    return RunbookRecommendationEngine(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # MatchCriteria (5)
    def test_criteria_symptom(self):
        assert MatchCriteria.SYMPTOM_MATCH == "symptom_match"

    def test_criteria_service(self):
        assert MatchCriteria.SERVICE_MATCH == "service_match"

    def test_criteria_error_pattern(self):
        assert MatchCriteria.ERROR_PATTERN == "error_pattern"

    def test_criteria_historical(self):
        assert MatchCriteria.HISTORICAL_SUCCESS == "historical_success"

    def test_criteria_keyword(self):
        assert MatchCriteria.KEYWORD_MATCH == "keyword_match"

    # RecommendationConfidence (5)
    def test_confidence_high(self):
        assert RecommendationConfidence.HIGH == "high"

    def test_confidence_moderate(self):
        assert RecommendationConfidence.MODERATE == "moderate"

    def test_confidence_low(self):
        assert RecommendationConfidence.LOW == "low"

    def test_confidence_speculative(self):
        assert RecommendationConfidence.SPECULATIVE == "speculative"

    def test_confidence_no_match(self):
        assert RecommendationConfidence.NO_MATCH == "no_match"

    # RunbookRelevance (5)
    def test_relevance_exact(self):
        assert RunbookRelevance.EXACT_FIT == "exact_fit"

    def test_relevance_good(self):
        assert RunbookRelevance.GOOD_FIT == "good_fit"

    def test_relevance_partial(self):
        assert RunbookRelevance.PARTIAL_FIT == "partial_fit"

    def test_relevance_related(self):
        assert RunbookRelevance.RELATED == "related"

    def test_relevance_generic(self):
        assert RunbookRelevance.GENERIC == "generic"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_recommendation_record_defaults(self):
        r = RecommendationRecord()
        assert r.id
        assert r.service_name == ""
        assert r.criteria == MatchCriteria.KEYWORD_MATCH
        assert r.confidence == RecommendationConfidence.LOW
        assert r.relevance == RunbookRelevance.GENERIC
        assert r.accuracy_score == 0.0
        assert r.details == ""
        assert r.created_at > 0

    def test_runbook_match_defaults(self):
        m = RunbookMatch()
        assert m.id
        assert m.match_name == ""
        assert m.criteria == MatchCriteria.KEYWORD_MATCH
        assert m.confidence == RecommendationConfidence.LOW
        assert m.effectiveness_score == 0.0
        assert m.description == ""
        assert m.created_at > 0

    def test_report_defaults(self):
        r = RunbookRecommenderReport()
        assert r.total_recommendations == 0
        assert r.total_matches == 0
        assert r.avg_accuracy_pct == 0.0
        assert r.by_criteria == {}
        assert r.by_confidence == {}
        assert r.high_accuracy_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_recommendation
# -------------------------------------------------------------------


class TestRecordRecommendation:
    def test_basic(self):
        eng = _engine()
        r = eng.record_recommendation(
            "svc-a",
            criteria=MatchCriteria.SYMPTOM_MATCH,
            confidence=RecommendationConfidence.HIGH,
            accuracy_score=85.0,
        )
        assert r.service_name == "svc-a"
        assert r.criteria == MatchCriteria.SYMPTOM_MATCH
        assert r.accuracy_score == 85.0

    def test_with_relevance(self):
        eng = _engine()
        r = eng.record_recommendation("svc-b", relevance=RunbookRelevance.EXACT_FIT)
        assert r.relevance == RunbookRelevance.EXACT_FIT

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_recommendation(f"svc-{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_recommendation
# -------------------------------------------------------------------


class TestGetRecommendation:
    def test_found(self):
        eng = _engine()
        r = eng.record_recommendation("svc-a")
        assert eng.get_recommendation(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_recommendation("nonexistent") is None


# -------------------------------------------------------------------
# list_recommendations
# -------------------------------------------------------------------


class TestListRecommendations:
    def test_list_all(self):
        eng = _engine()
        eng.record_recommendation("svc-a")
        eng.record_recommendation("svc-b")
        assert len(eng.list_recommendations()) == 2

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_recommendation("svc-a")
        eng.record_recommendation("svc-b")
        results = eng.list_recommendations(service_name="svc-a")
        assert len(results) == 1

    def test_filter_by_criteria(self):
        eng = _engine()
        eng.record_recommendation("svc-a", criteria=MatchCriteria.SYMPTOM_MATCH)
        eng.record_recommendation("svc-b", criteria=MatchCriteria.KEYWORD_MATCH)
        results = eng.list_recommendations(criteria=MatchCriteria.SYMPTOM_MATCH)
        assert len(results) == 1


# -------------------------------------------------------------------
# add_match
# -------------------------------------------------------------------


class TestAddMatch:
    def test_basic(self):
        eng = _engine()
        m = eng.add_match("restart-runbook", effectiveness_score=90.0)
        assert m.match_name == "restart-runbook"
        assert m.effectiveness_score == 90.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_match(f"match-{i}")
        assert len(eng._matches) == 2


# -------------------------------------------------------------------
# analyze_recommendation_accuracy
# -------------------------------------------------------------------


class TestAnalyzeRecommendationAccuracy:
    def test_with_data(self):
        eng = _engine(min_confidence_pct=60.0)
        eng.record_recommendation("svc-a", accuracy_score=70.0)
        eng.record_recommendation("svc-a", accuracy_score=80.0)
        result = eng.analyze_recommendation_accuracy("svc-a")
        assert result["service_name"] == "svc-a"
        assert result["total"] == 2
        assert result["avg_accuracy"] == 75.0
        assert result["meets_threshold"] is True

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_recommendation_accuracy("ghost")
        assert result["status"] == "no_data"


# -------------------------------------------------------------------
# identify_top_runbooks
# -------------------------------------------------------------------


class TestIdentifyTopRunbooks:
    def test_with_high_confidence(self):
        eng = _engine()
        eng.record_recommendation("svc-a", confidence=RecommendationConfidence.HIGH)
        eng.record_recommendation("svc-a", confidence=RecommendationConfidence.MODERATE)
        eng.record_recommendation("svc-b", confidence=RecommendationConfidence.LOW)
        results = eng.identify_top_runbooks()
        assert len(results) == 1
        assert results[0]["service_name"] == "svc-a"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_top_runbooks() == []


# -------------------------------------------------------------------
# rank_by_effectiveness
# -------------------------------------------------------------------


class TestRankByEffectiveness:
    def test_with_data(self):
        eng = _engine()
        eng.record_recommendation("svc-a", accuracy_score=10.0)
        eng.record_recommendation("svc-b", accuracy_score=90.0)
        results = eng.rank_by_effectiveness()
        assert results[0]["avg_accuracy_score"] == 90.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_effectiveness() == []


# -------------------------------------------------------------------
# detect_recommendation_gaps
# -------------------------------------------------------------------


class TestDetectRecommendationGaps:
    def test_with_gaps(self):
        eng = _engine()
        for _ in range(4):
            eng.record_recommendation("svc-gap")
        eng.record_recommendation("svc-ok")
        results = eng.detect_recommendation_gaps()
        assert len(results) == 1
        assert results[0]["service_name"] == "svc-gap"

    def test_empty(self):
        eng = _engine()
        assert eng.detect_recommendation_gaps() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine(min_confidence_pct=60.0)
        eng.record_recommendation(
            "svc-a",
            confidence=RecommendationConfidence.LOW,
            accuracy_score=80.0,
        )
        eng.record_recommendation(
            "svc-b",
            confidence=RecommendationConfidence.NO_MATCH,
            accuracy_score=10.0,
        )
        eng.add_match("match-1")
        report = eng.generate_report()
        assert isinstance(report, RunbookRecommenderReport)
        assert report.total_recommendations == 2
        assert report.total_matches == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert "performing well" in report.recommendations[0]


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_recommendation("svc-a")
        eng.add_match("match-1")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._matches) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_recommendations"] == 0
        assert stats["total_matches"] == 0
        assert stats["criteria_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_recommendation("svc-a", criteria=MatchCriteria.SYMPTOM_MATCH)
        eng.record_recommendation("svc-b", criteria=MatchCriteria.KEYWORD_MATCH)
        eng.add_match("match-1")
        stats = eng.get_stats()
        assert stats["total_recommendations"] == 2
        assert stats["total_matches"] == 1
        assert stats["unique_services"] == 2
