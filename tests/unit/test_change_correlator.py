"""Tests for shieldops.changes.change_correlator — ChangeCorrelationEngine."""

from __future__ import annotations

from shieldops.changes.change_correlator import (
    ChangeCorrelationEngine,
    ChangeCorrelationReport,
    ChangeOutcome,
    CorrelationPattern,
    CorrelationRecord,
    CorrelationStrength,
    CorrelationType,
)


def _engine(**kw) -> ChangeCorrelationEngine:
    return ChangeCorrelationEngine(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_type_causal(self):
        assert CorrelationType.CAUSAL == "causal"

    def test_type_temporal(self):
        assert CorrelationType.TEMPORAL == "temporal"

    def test_type_spatial(self):
        assert CorrelationType.SPATIAL == "spatial"

    def test_type_behavioral(self):
        assert CorrelationType.BEHAVIORAL == "behavioral"

    def test_type_coincidental(self):
        assert CorrelationType.COINCIDENTAL == "coincidental"

    def test_strength_strong(self):
        assert CorrelationStrength.STRONG == "strong"

    def test_strength_moderate(self):
        assert CorrelationStrength.MODERATE == "moderate"

    def test_strength_weak(self):
        assert CorrelationStrength.WEAK == "weak"

    def test_strength_negligible(self):
        assert CorrelationStrength.NEGLIGIBLE == "negligible"

    def test_strength_unknown(self):
        assert CorrelationStrength.UNKNOWN == "unknown"

    def test_outcome_success(self):
        assert ChangeOutcome.SUCCESS == "success"

    def test_outcome_partial_success(self):
        assert ChangeOutcome.PARTIAL_SUCCESS == "partial_success"

    def test_outcome_failure(self):
        assert ChangeOutcome.FAILURE == "failure"

    def test_outcome_rollback(self):
        assert ChangeOutcome.ROLLBACK == "rollback"

    def test_outcome_pending(self):
        assert ChangeOutcome.PENDING == "pending"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_correlation_record_defaults(self):
        r = CorrelationRecord()
        assert r.id
        assert r.change_id == ""
        assert r.incident_id == ""
        assert r.correlation_type == CorrelationType.CAUSAL
        assert r.strength == CorrelationStrength.UNKNOWN
        assert r.outcome == ChangeOutcome.PENDING
        assert r.team == ""
        assert r.created_at > 0

    def test_correlation_pattern_defaults(self):
        p = CorrelationPattern()
        assert p.id
        assert p.pattern_name == ""
        assert p.correlation_type == CorrelationType.CAUSAL
        assert p.occurrence_count == 0
        assert p.avg_strength_score == 0.0
        assert p.created_at > 0

    def test_correlation_report_defaults(self):
        r = ChangeCorrelationReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_patterns == 0
        assert r.strong_correlations == 0
        assert r.causal_pct == 0.0
        assert r.by_type == {}
        assert r.by_strength == {}
        assert r.by_outcome == {}
        assert r.high_risk_changes == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_correlation
# ---------------------------------------------------------------------------


class TestRecordCorrelation:
    def test_basic(self):
        eng = _engine()
        r = eng.record_correlation(
            change_id="CHG-001",
            incident_id="INC-001",
            correlation_type=CorrelationType.CAUSAL,
            strength=CorrelationStrength.STRONG,
            outcome=ChangeOutcome.FAILURE,
            team="sre",
        )
        assert r.change_id == "CHG-001"
        assert r.incident_id == "INC-001"
        assert r.correlation_type == CorrelationType.CAUSAL
        assert r.strength == CorrelationStrength.STRONG
        assert r.outcome == ChangeOutcome.FAILURE
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_correlation(change_id=f"CHG-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_correlation
# ---------------------------------------------------------------------------


class TestGetCorrelation:
    def test_found(self):
        eng = _engine()
        r = eng.record_correlation(
            change_id="CHG-001",
            strength=CorrelationStrength.STRONG,
        )
        result = eng.get_correlation(r.id)
        assert result is not None
        assert result.strength == CorrelationStrength.STRONG

    def test_not_found(self):
        eng = _engine()
        assert eng.get_correlation("nonexistent") is None


# ---------------------------------------------------------------------------
# list_correlations
# ---------------------------------------------------------------------------


class TestListCorrelations:
    def test_list_all(self):
        eng = _engine()
        eng.record_correlation(change_id="CHG-001")
        eng.record_correlation(change_id="CHG-002")
        assert len(eng.list_correlations()) == 2

    def test_filter_by_type(self):
        eng = _engine()
        eng.record_correlation(
            change_id="CHG-001",
            correlation_type=CorrelationType.CAUSAL,
        )
        eng.record_correlation(
            change_id="CHG-002",
            correlation_type=CorrelationType.TEMPORAL,
        )
        results = eng.list_correlations(
            correlation_type=CorrelationType.CAUSAL,
        )
        assert len(results) == 1

    def test_filter_by_strength(self):
        eng = _engine()
        eng.record_correlation(
            change_id="CHG-001",
            strength=CorrelationStrength.STRONG,
        )
        eng.record_correlation(
            change_id="CHG-002",
            strength=CorrelationStrength.WEAK,
        )
        results = eng.list_correlations(
            strength=CorrelationStrength.STRONG,
        )
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_correlation(change_id="CHG-001", team="sre")
        eng.record_correlation(change_id="CHG-002", team="platform")
        results = eng.list_correlations(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_correlation(change_id=f"CHG-{i}")
        assert len(eng.list_correlations(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_pattern
# ---------------------------------------------------------------------------


class TestAddPattern:
    def test_basic(self):
        eng = _engine()
        p = eng.add_pattern(
            pattern_name="deploy-failure",
            correlation_type=CorrelationType.CAUSAL,
            occurrence_count=5,
            avg_strength_score=0.85,
        )
        assert p.pattern_name == "deploy-failure"
        assert p.correlation_type == CorrelationType.CAUSAL
        assert p.occurrence_count == 5
        assert p.avg_strength_score == 0.85

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_pattern(pattern_name=f"pat-{i}")
        assert len(eng._patterns) == 2


# ---------------------------------------------------------------------------
# analyze_correlation_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeCorrelationDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_correlation(
            change_id="CHG-001",
            correlation_type=CorrelationType.CAUSAL,
            strength=CorrelationStrength.STRONG,
        )
        eng.record_correlation(
            change_id="CHG-002",
            correlation_type=CorrelationType.CAUSAL,
            strength=CorrelationStrength.MODERATE,
        )
        result = eng.analyze_correlation_distribution()
        assert "causal" in result
        assert result["causal"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_correlation_distribution() == {}


# ---------------------------------------------------------------------------
# identify_strong_correlations
# ---------------------------------------------------------------------------


class TestIdentifyStrongCorrelations:
    def test_detects_strong(self):
        eng = _engine()
        eng.record_correlation(
            change_id="CHG-001",
            strength=CorrelationStrength.STRONG,
        )
        eng.record_correlation(
            change_id="CHG-002",
            strength=CorrelationStrength.WEAK,
        )
        results = eng.identify_strong_correlations()
        assert len(results) == 1
        assert results[0]["change_id"] == "CHG-001"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_strong_correlations() == []


# ---------------------------------------------------------------------------
# rank_by_incident_impact
# ---------------------------------------------------------------------------


class TestRankByIncidentImpact:
    def test_ranked_descending(self):
        eng = _engine()
        eng.record_correlation(change_id="CHG-001", incident_id="INC-001")
        eng.record_correlation(change_id="CHG-001", incident_id="INC-002")
        eng.record_correlation(change_id="CHG-002", incident_id="INC-003")
        results = eng.rank_by_incident_impact()
        assert len(results) == 2
        assert results[0]["change_id"] == "CHG-001"
        assert results[0]["incident_count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_incident_impact() == []


# ---------------------------------------------------------------------------
# detect_correlation_trends
# ---------------------------------------------------------------------------


class TestDetectCorrelationTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.record_correlation(
                change_id="CHG-001",
                strength=CorrelationStrength.MODERATE,
            )
        result = eng.detect_correlation_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.record_correlation(
            change_id="CHG-001",
            strength=CorrelationStrength.WEAK,
        )
        eng.record_correlation(
            change_id="CHG-002",
            strength=CorrelationStrength.WEAK,
        )
        eng.record_correlation(
            change_id="CHG-003",
            strength=CorrelationStrength.STRONG,
        )
        eng.record_correlation(
            change_id="CHG-004",
            strength=CorrelationStrength.STRONG,
        )
        result = eng.detect_correlation_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_correlation_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_correlation(
            change_id="CHG-001",
            correlation_type=CorrelationType.CAUSAL,
            strength=CorrelationStrength.STRONG,
            outcome=ChangeOutcome.FAILURE,
        )
        report = eng.generate_report()
        assert isinstance(report, ChangeCorrelationReport)
        assert report.total_records == 1
        assert report.strong_correlations == 1
        assert len(report.high_risk_changes) == 1
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
        eng.record_correlation(change_id="CHG-001")
        eng.add_pattern(pattern_name="pat-1")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._patterns) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_patterns"] == 0
        assert stats["type_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_correlation(
            change_id="CHG-001",
            correlation_type=CorrelationType.CAUSAL,
            team="sre",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_changes"] == 1
        assert "causal" in stats["type_distribution"]
