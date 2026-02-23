"""Tests for the incident impact scorer module.

Covers:
- ImpactLevel enum values
- ImpactCategory enum values
- ImpactDimension model defaults
- ImpactScore model defaults
- LEVEL_WEIGHTS values
- _score_to_level() boundary tests
- IncidentImpactScorer creation
- score_incident() with dimensions, empty, max limit, clamped scores
- score_from_topology() basic, single service, many services, with revenue
- get_score() found and not found
- list_by_severity() at each level, limit
- get_stats() counts
- Weighted score computation correctness
- blast_radius capping at 1.0
"""

from __future__ import annotations

import pytest

from shieldops.agents.investigation.impact_scorer import (
    LEVEL_WEIGHTS,
    ImpactCategory,
    ImpactDimension,
    ImpactLevel,
    ImpactScore,
    IncidentImpactScorer,
    _score_to_level,
)

# ── Fixtures ─────────────────────────────────────────────────────


@pytest.fixture()
def scorer() -> IncidentImpactScorer:
    """Return a fresh IncidentImpactScorer."""
    return IncidentImpactScorer()


@pytest.fixture()
def populated_scorer() -> IncidentImpactScorer:
    """Return a scorer with several scored incidents."""
    s = IncidentImpactScorer()
    s.score_incident(
        incident_id="inc-001",
        dimensions=[
            {"category": "availability", "score": 0.9, "description": "Major outage"},
            {"category": "financial", "score": 0.7, "description": "Revenue loss"},
        ],
        affected_services=["api", "web", "db"],
        estimated_users_affected=5000,
        estimated_revenue_impact=50000.0,
    )
    s.score_incident(
        incident_id="inc-002",
        dimensions=[
            {"category": "performance", "score": 0.3, "description": "Slow responses"},
        ],
        affected_services=["api"],
    )
    s.score_incident(
        incident_id="inc-003",
        dimensions=[
            {"category": "security", "score": 0.1, "description": "Minor scan"},
        ],
    )
    return s


# ── Enum Tests ───────────────────────────────────────────────────


class TestImpactLevelEnum:
    def test_negligible_value(self) -> None:
        assert ImpactLevel.NEGLIGIBLE == "negligible"

    def test_low_value(self) -> None:
        assert ImpactLevel.LOW == "low"

    def test_moderate_value(self) -> None:
        assert ImpactLevel.MODERATE == "moderate"

    def test_high_value(self) -> None:
        assert ImpactLevel.HIGH == "high"

    def test_critical_value(self) -> None:
        assert ImpactLevel.CRITICAL == "critical"

    def test_all_members(self) -> None:
        members = {m.value for m in ImpactLevel}
        assert members == {"negligible", "low", "moderate", "high", "critical"}


class TestImpactCategoryEnum:
    def test_availability_value(self) -> None:
        assert ImpactCategory.AVAILABILITY == "availability"

    def test_performance_value(self) -> None:
        assert ImpactCategory.PERFORMANCE == "performance"

    def test_data_integrity_value(self) -> None:
        assert ImpactCategory.DATA_INTEGRITY == "data_integrity"

    def test_security_value(self) -> None:
        assert ImpactCategory.SECURITY == "security"

    def test_financial_value(self) -> None:
        assert ImpactCategory.FINANCIAL == "financial"


# ── Model Tests ──────────────────────────────────────────────────


class TestImpactDimensionModel:
    def test_defaults(self) -> None:
        dim = ImpactDimension(category=ImpactCategory.AVAILABILITY)
        assert dim.score == 0.0
        assert dim.level == ImpactLevel.NEGLIGIBLE
        assert dim.description == ""
        assert dim.affected_users == 0
        assert dim.metadata == {}

    def test_full_creation(self) -> None:
        dim = ImpactDimension(
            category=ImpactCategory.SECURITY,
            score=0.85,
            level=ImpactLevel.CRITICAL,
            description="Breach detected",
            affected_users=10000,
            metadata={"vector": "network"},
        )
        assert dim.score == 0.85
        assert dim.level == ImpactLevel.CRITICAL
        assert dim.affected_users == 10000


class TestImpactScoreModel:
    def test_defaults(self) -> None:
        score = ImpactScore(incident_id="inc-1")
        assert score.incident_id == "inc-1"
        assert score.overall_score == 0.0
        assert score.overall_level == ImpactLevel.NEGLIGIBLE
        assert score.dimensions == []
        assert score.affected_services == []
        assert score.estimated_users_affected == 0
        assert score.estimated_revenue_impact == 0.0
        assert score.blast_radius == 0.0
        assert score.scored_at > 0
        assert score.metadata == {}
        assert len(score.id) == 12


# ── LEVEL_WEIGHTS ────────────────────────────────────────────────


class TestLevelWeights:
    def test_availability_weight(self) -> None:
        assert LEVEL_WEIGHTS[ImpactCategory.AVAILABILITY] == 1.0

    def test_performance_weight(self) -> None:
        assert LEVEL_WEIGHTS[ImpactCategory.PERFORMANCE] == 0.7

    def test_data_integrity_weight(self) -> None:
        assert LEVEL_WEIGHTS[ImpactCategory.DATA_INTEGRITY] == 0.9

    def test_security_weight(self) -> None:
        assert LEVEL_WEIGHTS[ImpactCategory.SECURITY] == 1.0

    def test_financial_weight(self) -> None:
        assert LEVEL_WEIGHTS[ImpactCategory.FINANCIAL] == 0.8

    def test_all_categories_present(self) -> None:
        for cat in ImpactCategory:
            assert cat in LEVEL_WEIGHTS


# ── _score_to_level ──────────────────────────────────────────────


class TestScoreToLevel:
    def test_critical_at_0_8(self) -> None:
        assert _score_to_level(0.8) == ImpactLevel.CRITICAL

    def test_critical_above_0_8(self) -> None:
        assert _score_to_level(1.0) == ImpactLevel.CRITICAL

    def test_high_at_0_6(self) -> None:
        assert _score_to_level(0.6) == ImpactLevel.HIGH

    def test_high_at_0_79(self) -> None:
        assert _score_to_level(0.79) == ImpactLevel.HIGH

    def test_moderate_at_0_4(self) -> None:
        assert _score_to_level(0.4) == ImpactLevel.MODERATE

    def test_low_at_0_2(self) -> None:
        assert _score_to_level(0.2) == ImpactLevel.LOW

    def test_negligible_at_0(self) -> None:
        assert _score_to_level(0.0) == ImpactLevel.NEGLIGIBLE

    def test_negligible_at_0_19(self) -> None:
        assert _score_to_level(0.19) == ImpactLevel.NEGLIGIBLE

    def test_negative_score(self) -> None:
        assert _score_to_level(-0.5) == ImpactLevel.NEGLIGIBLE


# ── Scorer Creation ──────────────────────────────────────────────


class TestScorerCreation:
    def test_default_max_records(self) -> None:
        s = IncidentImpactScorer()
        assert s._max_records == 10000

    def test_custom_max_records(self) -> None:
        s = IncidentImpactScorer(max_records=5)
        assert s._max_records == 5

    def test_starts_empty(self) -> None:
        s = IncidentImpactScorer()
        assert len(s._scores) == 0


# ── score_incident ───────────────────────────────────────────────


class TestScoreIncident:
    def test_with_single_dimension(self, scorer: IncidentImpactScorer) -> None:
        result = scorer.score_incident(
            incident_id="inc-1",
            dimensions=[{"category": "availability", "score": 0.5}],
        )
        assert result.incident_id == "inc-1"
        assert len(result.dimensions) == 1
        assert result.dimensions[0].score == 0.5
        assert result.dimensions[0].category == ImpactCategory.AVAILABILITY
        assert result.overall_score == pytest.approx(0.5, abs=0.01)

    def test_with_multiple_dimensions(self, scorer: IncidentImpactScorer) -> None:
        result = scorer.score_incident(
            incident_id="inc-1",
            dimensions=[
                {"category": "availability", "score": 1.0},
                {"category": "performance", "score": 0.5},
            ],
        )
        # Weighted: (1.0*1.0 + 0.5*0.7) / (1.0+0.7) = 1.35/1.7
        expected = (1.0 * 1.0 + 0.5 * 0.7) / (1.0 + 0.7)
        assert result.overall_score == pytest.approx(expected, abs=0.01)

    def test_empty_dimensions(self, scorer: IncidentImpactScorer) -> None:
        result = scorer.score_incident(incident_id="inc-1", dimensions=[])
        assert result.overall_score == pytest.approx(0.0)
        assert result.overall_level == ImpactLevel.NEGLIGIBLE
        assert result.dimensions == []

    def test_no_dimensions_param(self, scorer: IncidentImpactScorer) -> None:
        result = scorer.score_incident(incident_id="inc-1")
        assert result.overall_score == pytest.approx(0.0)

    def test_max_limit_raises(self) -> None:
        s = IncidentImpactScorer(max_records=2)
        s.score_incident(incident_id="inc-1")
        s.score_incident(incident_id="inc-2")
        with pytest.raises(ValueError, match="Maximum records limit reached"):
            s.score_incident(incident_id="inc-3")

    def test_score_clamped_above_1(self, scorer: IncidentImpactScorer) -> None:
        result = scorer.score_incident(
            incident_id="inc-1",
            dimensions=[{"category": "availability", "score": 1.5}],
        )
        assert result.dimensions[0].score == 1.0, "Score should be clamped to 1.0"

    def test_score_clamped_below_0(self, scorer: IncidentImpactScorer) -> None:
        result = scorer.score_incident(
            incident_id="inc-1",
            dimensions=[{"category": "availability", "score": -0.5}],
        )
        assert result.dimensions[0].score == 0.0, "Score should be clamped to 0.0"

    def test_affected_services_stored(self, scorer: IncidentImpactScorer) -> None:
        result = scorer.score_incident(
            incident_id="inc-1",
            affected_services=["api", "web"],
        )
        assert result.affected_services == ["api", "web"]

    def test_blast_radius_computed(self, scorer: IncidentImpactScorer) -> None:
        result = scorer.score_incident(
            incident_id="inc-1",
            affected_services=["s1", "s2", "s3"],
        )
        assert result.blast_radius == pytest.approx(0.3, abs=0.01)

    def test_blast_radius_capped_at_1(self, scorer: IncidentImpactScorer) -> None:
        services = [f"svc-{i}" for i in range(15)]
        result = scorer.score_incident(
            incident_id="inc-1",
            affected_services=services,
        )
        assert result.blast_radius == pytest.approx(1.0)

    def test_blast_radius_zero_no_services(self, scorer: IncidentImpactScorer) -> None:
        result = scorer.score_incident(incident_id="inc-1")
        assert result.blast_radius == pytest.approx(0.0)

    def test_metadata_stored(self, scorer: IncidentImpactScorer) -> None:
        result = scorer.score_incident(
            incident_id="inc-1",
            metadata={"source": "pagerduty"},
        )
        assert result.metadata == {"source": "pagerduty"}

    def test_estimated_users_affected(self, scorer: IncidentImpactScorer) -> None:
        result = scorer.score_incident(
            incident_id="inc-1",
            estimated_users_affected=1000,
        )
        assert result.estimated_users_affected == 1000

    def test_estimated_revenue_impact(self, scorer: IncidentImpactScorer) -> None:
        result = scorer.score_incident(
            incident_id="inc-1",
            estimated_revenue_impact=25000.0,
        )
        assert result.estimated_revenue_impact == pytest.approx(25000.0)

    def test_dimension_level_auto_set(self, scorer: IncidentImpactScorer) -> None:
        result = scorer.score_incident(
            incident_id="inc-1",
            dimensions=[{"category": "availability", "score": 0.85}],
        )
        assert result.dimensions[0].level == ImpactLevel.CRITICAL

    def test_overall_level_from_score(self, scorer: IncidentImpactScorer) -> None:
        result = scorer.score_incident(
            incident_id="inc-1",
            dimensions=[{"category": "availability", "score": 0.9}],
        )
        assert result.overall_level == ImpactLevel.CRITICAL

    def test_returns_impact_score_instance(self, scorer: IncidentImpactScorer) -> None:
        result = scorer.score_incident(incident_id="inc-1")
        assert isinstance(result, ImpactScore)


# ── score_from_topology ──────────────────────────────────────────


class TestScoreFromTopology:
    def test_basic(self, scorer: IncidentImpactScorer) -> None:
        result = scorer.score_from_topology(
            incident_id="inc-1",
            affected_services=["api", "web"],
            total_services=10,
        )
        assert result.incident_id == "inc-1"
        assert len(result.dimensions) == 2
        assert result.dimensions[0].category == ImpactCategory.AVAILABILITY
        assert result.dimensions[0].score == pytest.approx(0.2)
        assert result.estimated_users_affected == 200  # 2 * 100

    def test_single_service(self, scorer: IncidentImpactScorer) -> None:
        result = scorer.score_from_topology(
            incident_id="inc-1",
            affected_services=["api"],
            total_services=5,
        )
        assert result.dimensions[0].score == pytest.approx(0.2)
        assert result.estimated_users_affected == 100

    def test_many_services_all_affected(self, scorer: IncidentImpactScorer) -> None:
        services = [f"svc-{i}" for i in range(10)]
        result = scorer.score_from_topology(
            incident_id="inc-1",
            affected_services=services,
            total_services=10,
        )
        assert result.dimensions[0].score == pytest.approx(1.0)

    def test_with_revenue(self, scorer: IncidentImpactScorer) -> None:
        result = scorer.score_from_topology(
            incident_id="inc-1",
            affected_services=["api", "web"],
            total_services=10,
            revenue_per_service_hour=5000.0,
        )
        assert result.estimated_revenue_impact == pytest.approx(10000.0)
        # Financial dimension score: min(10000 / 10000, 1.0) = 1.0
        financial_dim = result.dimensions[1]
        assert financial_dim.category == ImpactCategory.FINANCIAL
        assert financial_dim.score == pytest.approx(1.0)

    def test_zero_revenue(self, scorer: IncidentImpactScorer) -> None:
        result = scorer.score_from_topology(
            incident_id="inc-1",
            affected_services=["api"],
            total_services=5,
            revenue_per_service_hour=0.0,
        )
        financial_dim = result.dimensions[1]
        assert financial_dim.score == pytest.approx(0.0)

    def test_custom_users_per_service(self, scorer: IncidentImpactScorer) -> None:
        result = scorer.score_from_topology(
            incident_id="inc-1",
            affected_services=["api"],
            total_services=5,
            users_per_service=500,
        )
        assert result.estimated_users_affected == 500

    def test_total_services_defaults_to_affected_count(self, scorer: IncidentImpactScorer) -> None:
        result = scorer.score_from_topology(
            incident_id="inc-1",
            affected_services=["api", "web", "db"],
        )
        # total = max(0, 3) = 3, availability = 3/3 = 1.0
        assert result.dimensions[0].score == pytest.approx(1.0)

    def test_metadata_passed_through(self, scorer: IncidentImpactScorer) -> None:
        result = scorer.score_from_topology(
            incident_id="inc-1",
            affected_services=["api"],
            metadata={"source": "topology"},
        )
        assert result.metadata == {"source": "topology"}


# ── get_score ────────────────────────────────────────────────────


class TestGetScore:
    def test_found(self, populated_scorer: IncidentImpactScorer) -> None:
        result = populated_scorer.get_score("inc-001")
        assert result is not None
        assert result.incident_id == "inc-001"

    def test_not_found(self, populated_scorer: IncidentImpactScorer) -> None:
        assert populated_scorer.get_score("nonexistent") is None

    def test_empty_scorer(self, scorer: IncidentImpactScorer) -> None:
        assert scorer.get_score("any") is None


# ── list_by_severity ─────────────────────────────────────────────


class TestListBySeverity:
    def test_all_levels(self, populated_scorer: IncidentImpactScorer) -> None:
        # NEGLIGIBLE is the highest index; all incidents should have level <= that
        results = populated_scorer.list_by_severity(min_level=ImpactLevel.NEGLIGIBLE)
        assert len(results) == 3

    def test_critical_only(self, populated_scorer: IncidentImpactScorer) -> None:
        results = populated_scorer.list_by_severity(min_level=ImpactLevel.CRITICAL)
        # Only inc-001 has critical overall score
        assert all(r.overall_level == ImpactLevel.CRITICAL for r in results)

    def test_sorted_by_score_desc(self, populated_scorer: IncidentImpactScorer) -> None:
        results = populated_scorer.list_by_severity()
        for i in range(len(results) - 1):
            assert results[i].overall_score >= results[i + 1].overall_score

    def test_limit(self, populated_scorer: IncidentImpactScorer) -> None:
        results = populated_scorer.list_by_severity(limit=1)
        assert len(results) == 1

    def test_empty_scorer(self, scorer: IncidentImpactScorer) -> None:
        assert scorer.list_by_severity() == []


# ── get_stats ────────────────────────────────────────────────────


class TestGetStats:
    def test_empty_scorer(self, scorer: IncidentImpactScorer) -> None:
        stats = scorer.get_stats()
        assert stats["total_scores"] == 0
        assert stats["by_level"] == {}

    def test_populated(self, populated_scorer: IncidentImpactScorer) -> None:
        stats = populated_scorer.get_stats()
        assert stats["total_scores"] == 3
        # At least one level should be counted
        total_counted = sum(stats["by_level"].values())
        assert total_counted == 3

    def test_by_level_counts(self, scorer: IncidentImpactScorer) -> None:
        scorer.score_incident("i1", dimensions=[{"category": "availability", "score": 0.9}])
        scorer.score_incident("i2", dimensions=[{"category": "availability", "score": 0.9}])
        scorer.score_incident("i3", dimensions=[{"category": "availability", "score": 0.1}])
        stats = scorer.get_stats()
        assert stats["by_level"]["critical"] == 2
        assert stats["by_level"]["negligible"] == 1


# ── Weighted Score Computation ───────────────────────────────────


class TestWeightedScoreComputation:
    def test_single_category_weight(self, scorer: IncidentImpactScorer) -> None:
        result = scorer.score_incident(
            incident_id="inc-1",
            dimensions=[{"category": "performance", "score": 0.5}],
        )
        # (0.5 * 0.7) / 0.7 = 0.5
        assert result.overall_score == pytest.approx(0.5, abs=0.01)

    def test_mixed_weights(self, scorer: IncidentImpactScorer) -> None:
        result = scorer.score_incident(
            incident_id="inc-1",
            dimensions=[
                {"category": "availability", "score": 0.8},  # w=1.0
                {"category": "performance", "score": 0.4},  # w=0.7
                {"category": "data_integrity", "score": 0.6},  # w=0.9
                {"category": "security", "score": 0.2},  # w=1.0
                {"category": "financial", "score": 0.5},  # w=0.8
            ],
        )
        weighted_sum = 0.8 * 1.0 + 0.4 * 0.7 + 0.6 * 0.9 + 0.2 * 1.0 + 0.5 * 0.8
        total_weight = 1.0 + 0.7 + 0.9 + 1.0 + 0.8
        expected = weighted_sum / total_weight
        assert result.overall_score == pytest.approx(expected, abs=0.001)

    def test_all_zeros(self, scorer: IncidentImpactScorer) -> None:
        result = scorer.score_incident(
            incident_id="inc-1",
            dimensions=[
                {"category": "availability", "score": 0.0},
                {"category": "security", "score": 0.0},
            ],
        )
        assert result.overall_score == pytest.approx(0.0)

    def test_all_max(self, scorer: IncidentImpactScorer) -> None:
        result = scorer.score_incident(
            incident_id="inc-1",
            dimensions=[
                {"category": "availability", "score": 1.0},
                {"category": "security", "score": 1.0},
            ],
        )
        assert result.overall_score == pytest.approx(1.0, abs=0.01)
