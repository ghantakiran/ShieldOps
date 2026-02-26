"""Tests for shieldops.incidents.incident_similarity — IncidentSimilarityEngine."""

from __future__ import annotations

from shieldops.incidents.incident_similarity import (
    IncidentSimilarityEngine,
    IncidentSimilarityReport,
    MatchConfidence,
    SimilarityDimension,
    SimilarityMatch,
    SimilarityRecord,
    SimilarityScope,
)


def _engine(**kw) -> IncidentSimilarityEngine:
    return IncidentSimilarityEngine(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # SimilarityDimension (5)
    def test_dimension_symptoms(self):
        assert SimilarityDimension.SYMPTOMS == "symptoms"

    def test_dimension_root_cause(self):
        assert SimilarityDimension.ROOT_CAUSE == "root_cause"

    def test_dimension_affected_services(self):
        assert SimilarityDimension.AFFECTED_SERVICES == "affected_services"

    def test_dimension_timeline_pattern(self):
        assert SimilarityDimension.TIMELINE_PATTERN == "timeline_pattern"

    def test_dimension_resolution_path(self):
        assert SimilarityDimension.RESOLUTION_PATH == "resolution_path"

    # MatchConfidence (5)
    def test_confidence_exact(self):
        assert MatchConfidence.EXACT == "exact"

    def test_confidence_high(self):
        assert MatchConfidence.HIGH == "high"

    def test_confidence_moderate(self):
        assert MatchConfidence.MODERATE == "moderate"

    def test_confidence_low(self):
        assert MatchConfidence.LOW == "low"

    def test_confidence_no_match(self):
        assert MatchConfidence.NO_MATCH == "no_match"

    # SimilarityScope (5)
    def test_scope_same_service(self):
        assert SimilarityScope.SAME_SERVICE == "same_service"

    def test_scope_same_team(self):
        assert SimilarityScope.SAME_TEAM == "same_team"

    def test_scope_same_category(self):
        assert SimilarityScope.SAME_CATEGORY == "same_category"

    def test_scope_cross_team(self):
        assert SimilarityScope.CROSS_TEAM == "cross_team"

    def test_scope_platform_wide(self):
        assert SimilarityScope.PLATFORM_WIDE == "platform_wide"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_similarity_record_defaults(self):
        r = SimilarityRecord()
        assert r.id
        assert r.service_name == ""
        assert r.dimension == SimilarityDimension.SYMPTOMS
        assert r.confidence == MatchConfidence.MODERATE
        assert r.scope == SimilarityScope.SAME_SERVICE
        assert r.match_score == 0.0
        assert r.details == ""
        assert r.created_at > 0

    def test_similarity_match_defaults(self):
        r = SimilarityMatch()
        assert r.id
        assert r.match_name == ""
        assert r.dimension == SimilarityDimension.SYMPTOMS
        assert r.confidence == MatchConfidence.MODERATE
        assert r.score == 0.0
        assert r.incident_id == ""
        assert r.created_at > 0

    def test_similarity_report_defaults(self):
        r = IncidentSimilarityReport()
        assert r.total_similarities == 0
        assert r.total_matches == 0
        assert r.avg_match_score_pct == 0.0
        assert r.by_dimension == {}
        assert r.by_confidence == {}
        assert r.high_confidence_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_similarity
# -------------------------------------------------------------------


class TestRecordSimilarity:
    def test_basic(self):
        eng = _engine()
        r = eng.record_similarity(
            "svc-a",
            dimension=SimilarityDimension.SYMPTOMS,
            confidence=MatchConfidence.HIGH,
        )
        assert r.service_name == "svc-a"
        assert r.dimension == SimilarityDimension.SYMPTOMS

    def test_with_scope(self):
        eng = _engine()
        r = eng.record_similarity("svc-b", scope=SimilarityScope.CROSS_TEAM)
        assert r.scope == SimilarityScope.CROSS_TEAM

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_similarity(f"svc-{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_similarity
# -------------------------------------------------------------------


class TestGetSimilarity:
    def test_found(self):
        eng = _engine()
        r = eng.record_similarity("svc-a")
        assert eng.get_similarity(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_similarity("nonexistent") is None


# -------------------------------------------------------------------
# list_similarities
# -------------------------------------------------------------------


class TestListSimilarities:
    def test_list_all(self):
        eng = _engine()
        eng.record_similarity("svc-a")
        eng.record_similarity("svc-b")
        assert len(eng.list_similarities()) == 2

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_similarity("svc-a")
        eng.record_similarity("svc-b")
        results = eng.list_similarities(service_name="svc-a")
        assert len(results) == 1

    def test_filter_by_dimension(self):
        eng = _engine()
        eng.record_similarity("svc-a", dimension=SimilarityDimension.ROOT_CAUSE)
        eng.record_similarity("svc-b", dimension=SimilarityDimension.SYMPTOMS)
        results = eng.list_similarities(dimension=SimilarityDimension.ROOT_CAUSE)
        assert len(results) == 1


# -------------------------------------------------------------------
# add_match
# -------------------------------------------------------------------


class TestAddMatch:
    def test_basic(self):
        eng = _engine()
        m = eng.add_match(
            "match-1",
            dimension=SimilarityDimension.SYMPTOMS,
            confidence=MatchConfidence.HIGH,
            score=85.0,
            incident_id="inc-1",
        )
        assert m.match_name == "match-1"
        assert m.score == 85.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_match(f"match-{i}")
        assert len(eng._matches) == 2


# -------------------------------------------------------------------
# analyze_similarity_patterns
# -------------------------------------------------------------------


class TestAnalyzeSimilarityPatterns:
    def test_with_data(self):
        eng = _engine()
        eng.record_similarity("svc-a", match_score=80.0, confidence=MatchConfidence.HIGH)
        eng.record_similarity("svc-a", match_score=60.0, confidence=MatchConfidence.LOW)
        result = eng.analyze_similarity_patterns("svc-a")
        assert result["service_name"] == "svc-a"
        assert result["total_records"] == 2
        assert result["avg_match_score"] == 70.0

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_similarity_patterns("ghost")
        assert result["status"] == "no_data"


# -------------------------------------------------------------------
# identify_high_confidence_matches
# -------------------------------------------------------------------


class TestIdentifyHighConfidenceMatches:
    def test_with_matches(self):
        eng = _engine()
        eng.record_similarity("svc-a", confidence=MatchConfidence.EXACT)
        eng.record_similarity("svc-a", confidence=MatchConfidence.HIGH)
        eng.record_similarity("svc-b", confidence=MatchConfidence.LOW)
        results = eng.identify_high_confidence_matches()
        assert len(results) == 1
        assert results[0]["service_name"] == "svc-a"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_high_confidence_matches() == []


# -------------------------------------------------------------------
# rank_by_match_score
# -------------------------------------------------------------------


class TestRankByMatchScore:
    def test_with_data(self):
        eng = _engine()
        eng.record_similarity("svc-a", match_score=90.0)
        eng.record_similarity("svc-a", match_score=80.0)
        eng.record_similarity("svc-b", match_score=50.0)
        results = eng.rank_by_match_score()
        assert results[0]["service_name"] == "svc-a"
        assert results[0]["avg_match_score"] == 85.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_match_score() == []


# -------------------------------------------------------------------
# detect_recurring_similarities
# -------------------------------------------------------------------


class TestDetectRecurringSimilarities:
    def test_with_recurring(self):
        eng = _engine()
        for _ in range(5):
            eng.record_similarity("svc-a")
        eng.record_similarity("svc-b")
        results = eng.detect_recurring_similarities()
        assert len(results) == 1
        assert results[0]["service_name"] == "svc-a"
        assert results[0]["recurring"] is True

    def test_no_recurring(self):
        eng = _engine()
        eng.record_similarity("svc-a")
        assert eng.detect_recurring_similarities() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine()
        eng.record_similarity("svc-a", confidence=MatchConfidence.HIGH, match_score=80.0)
        eng.record_similarity("svc-b", confidence=MatchConfidence.LOW, match_score=30.0)
        eng.add_match("match-1")
        report = eng.generate_report()
        assert report.total_similarities == 2
        assert report.total_matches == 1
        assert report.by_dimension != {}
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_similarities == 0
        assert "below" in report.recommendations[0]


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_similarity("svc-a")
        eng.add_match("match-1")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._matches) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_similarities"] == 0
        assert stats["total_matches"] == 0
        assert stats["dimension_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_similarity("svc-a", dimension=SimilarityDimension.SYMPTOMS)
        eng.record_similarity("svc-b", dimension=SimilarityDimension.ROOT_CAUSE)
        eng.add_match("m1")
        stats = eng.get_stats()
        assert stats["total_similarities"] == 2
        assert stats["total_matches"] == 1
        assert stats["unique_services"] == 2
