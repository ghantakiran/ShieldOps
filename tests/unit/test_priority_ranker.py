"""Tests for shieldops.incidents.priority_ranker — IncidentPriorityRanker."""

from __future__ import annotations

from shieldops.incidents.priority_ranker import (
    IncidentPriorityRanker,
    PriorityFactor,
    PriorityFactorDetail,
    PriorityLevel,
    PriorityRankerReport,
    PriorityRecord,
    RankingMethod,
)


def _engine(**kw) -> IncidentPriorityRanker:
    return IncidentPriorityRanker(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # PriorityLevel (5)
    def test_level_p0_critical(self):
        assert PriorityLevel.P0_CRITICAL == "p0_critical"

    def test_level_p1_high(self):
        assert PriorityLevel.P1_HIGH == "p1_high"

    def test_level_p2_medium(self):
        assert PriorityLevel.P2_MEDIUM == "p2_medium"

    def test_level_p3_low(self):
        assert PriorityLevel.P3_LOW == "p3_low"

    def test_level_p4_informational(self):
        assert PriorityLevel.P4_INFORMATIONAL == "p4_informational"

    # PriorityFactor (5)
    def test_factor_user_impact(self):
        assert PriorityFactor.USER_IMPACT == "user_impact"

    def test_factor_revenue_loss(self):
        assert PriorityFactor.REVENUE_LOSS == "revenue_loss"

    def test_factor_sla_risk(self):
        assert PriorityFactor.SLA_RISK == "sla_risk"

    def test_factor_security_exposure(self):
        assert PriorityFactor.SECURITY_EXPOSURE == "security_exposure"

    def test_factor_data_integrity(self):
        assert PriorityFactor.DATA_INTEGRITY == "data_integrity"

    # RankingMethod (5)
    def test_method_weighted_score(self):
        assert RankingMethod.WEIGHTED_SCORE == "weighted_score"

    def test_method_machine_learning(self):
        assert RankingMethod.MACHINE_LEARNING == "machine_learning"

    def test_method_rule_based(self):
        assert RankingMethod.RULE_BASED == "rule_based"

    def test_method_hybrid(self):
        assert RankingMethod.HYBRID == "hybrid"

    def test_method_manual(self):
        assert RankingMethod.MANUAL == "manual"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_priority_record_defaults(self):
        r = PriorityRecord()
        assert r.id
        assert r.incident_id == ""
        assert r.incident_title == ""
        assert r.assigned_priority == PriorityLevel.P2_MEDIUM
        assert r.computed_priority == PriorityLevel.P2_MEDIUM
        assert r.ranking_method == RankingMethod.WEIGHTED_SCORE
        assert r.priority_score == 0.0
        assert r.factors_used == []
        assert r.is_misranked is False
        assert r.created_at > 0

    def test_priority_factor_detail_defaults(self):
        r = PriorityFactorDetail()
        assert r.id
        assert r.factor_name == ""
        assert r.factor_type == PriorityFactor.USER_IMPACT
        assert r.weight == 1.0
        assert r.enabled is True
        assert r.created_at > 0

    def test_report_defaults(self):
        r = PriorityRankerReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_factors == 0
        assert r.misranked_count == 0
        assert r.accuracy_pct == 0.0
        assert r.by_assigned_priority == {}
        assert r.by_computed_priority == {}
        assert r.by_ranking_method == {}
        assert r.priority_drift_detected is False
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# -------------------------------------------------------------------
# record_priority
# -------------------------------------------------------------------


class TestRecordPriority:
    def test_basic(self):
        eng = _engine()
        r = eng.record_priority("INC-001")
        assert r.incident_id == "INC-001"
        assert r.assigned_priority == PriorityLevel.P2_MEDIUM

    def test_with_params(self):
        eng = _engine()
        r = eng.record_priority(
            "INC-002",
            incident_title="DB down",
            assigned_priority=PriorityLevel.P0_CRITICAL,
            computed_priority=PriorityLevel.P1_HIGH,
            ranking_method=RankingMethod.HYBRID,
            priority_score=95.0,
            is_misranked=True,
        )
        assert r.assigned_priority == PriorityLevel.P0_CRITICAL
        assert r.computed_priority == PriorityLevel.P1_HIGH
        assert r.priority_score == 95.0
        assert r.is_misranked is True

    def test_unique_ids(self):
        eng = _engine()
        r1 = eng.record_priority("INC-A")
        r2 = eng.record_priority("INC-B")
        assert r1.id != r2.id

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_priority(f"INC-{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_priority
# -------------------------------------------------------------------


class TestGetPriority:
    def test_found(self):
        eng = _engine()
        r = eng.record_priority("INC-001")
        assert eng.get_priority(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_priority("nonexistent") is None


# -------------------------------------------------------------------
# list_priorities
# -------------------------------------------------------------------


class TestListPriorities:
    def test_list_all(self):
        eng = _engine()
        eng.record_priority("INC-A")
        eng.record_priority("INC-B")
        assert len(eng.list_priorities()) == 2

    def test_filter_by_assigned_priority(self):
        eng = _engine()
        eng.record_priority("INC-A", assigned_priority=PriorityLevel.P0_CRITICAL)
        eng.record_priority("INC-B", assigned_priority=PriorityLevel.P3_LOW)
        results = eng.list_priorities(assigned_priority=PriorityLevel.P0_CRITICAL)
        assert len(results) == 1
        assert results[0].assigned_priority == PriorityLevel.P0_CRITICAL

    def test_filter_by_method(self):
        eng = _engine()
        eng.record_priority("INC-A", ranking_method=RankingMethod.RULE_BASED)
        eng.record_priority("INC-B", ranking_method=RankingMethod.MANUAL)
        results = eng.list_priorities(ranking_method=RankingMethod.RULE_BASED)
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_priority(f"INC-{i}")
        assert len(eng.list_priorities(limit=4)) == 4


# -------------------------------------------------------------------
# add_factor
# -------------------------------------------------------------------


class TestAddFactor:
    def test_basic(self):
        eng = _engine()
        f = eng.add_factor("user-impact-weight")
        assert f.factor_name == "user-impact-weight"
        assert f.factor_type == PriorityFactor.USER_IMPACT
        assert f.weight == 1.0
        assert f.enabled is True

    def test_with_params(self):
        eng = _engine()
        f = eng.add_factor(
            "revenue-factor",
            factor_type=PriorityFactor.REVENUE_LOSS,
            weight=3.0,
            description="Revenue impact multiplier",
        )
        assert f.factor_type == PriorityFactor.REVENUE_LOSS
        assert f.weight == 3.0

    def test_unique_ids(self):
        eng = _engine()
        f1 = eng.add_factor("factor-a")
        f2 = eng.add_factor("factor-b")
        assert f1.id != f2.id


# -------------------------------------------------------------------
# analyze_priority_distribution
# -------------------------------------------------------------------


class TestAnalyzePriorityDistribution:
    def test_empty(self):
        eng = _engine()
        result = eng.analyze_priority_distribution()
        assert result["total"] == 0

    def test_with_data(self):
        eng = _engine()
        eng.record_priority("INC-A", assigned_priority=PriorityLevel.P0_CRITICAL)
        eng.record_priority("INC-B", assigned_priority=PriorityLevel.P1_HIGH)
        eng.record_priority("INC-C", assigned_priority=PriorityLevel.P2_MEDIUM)
        result = eng.analyze_priority_distribution()
        assert result["total"] == 3
        assert result["p0_count"] == 1
        assert result["by_assigned"]

    def test_p0_ratio(self):
        eng = _engine()
        eng.record_priority("INC-A", assigned_priority=PriorityLevel.P0_CRITICAL)
        for _ in range(3):
            eng.record_priority("INC-X", assigned_priority=PriorityLevel.P2_MEDIUM)
        result = eng.analyze_priority_distribution()
        assert result["p0_ratio_pct"] == 25.0


# -------------------------------------------------------------------
# identify_misranked_incidents
# -------------------------------------------------------------------


class TestIdentifyMisrankedIncidents:
    def test_empty(self):
        eng = _engine()
        assert eng.identify_misranked_incidents() == []

    def test_with_mismatch(self):
        eng = _engine()
        eng.record_priority(
            "INC-A",
            assigned_priority=PriorityLevel.P0_CRITICAL,
            computed_priority=PriorityLevel.P2_MEDIUM,
        )
        eng.record_priority(
            "INC-B",
            assigned_priority=PriorityLevel.P1_HIGH,
            computed_priority=PriorityLevel.P1_HIGH,
        )
        results = eng.identify_misranked_incidents()
        assert len(results) == 1
        assert results[0]["incident_id"] == "INC-A"

    def test_flagged_misranked(self):
        eng = _engine()
        eng.record_priority("INC-C", is_misranked=True)
        results = eng.identify_misranked_incidents()
        assert len(results) == 1


# -------------------------------------------------------------------
# rank_by_priority_score
# -------------------------------------------------------------------


class TestRankByPriorityScore:
    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_priority_score() == []

    def test_sorted_descending(self):
        eng = _engine()
        eng.record_priority("INC-A", priority_score=10.0)
        eng.record_priority("INC-B", priority_score=90.0)
        eng.record_priority("INC-C", priority_score=50.0)
        results = eng.rank_by_priority_score()
        scores = [r["priority_score"] for r in results]
        assert scores == sorted(scores, reverse=True)
        assert results[0]["incident_id"] == "INC-B"


# -------------------------------------------------------------------
# detect_priority_drift
# -------------------------------------------------------------------


class TestDetectPriorityDrift:
    def test_insufficient_data(self):
        eng = _engine()
        eng.record_priority("INC-A")
        result = eng.detect_priority_drift()
        assert result["drift_detected"] is False
        assert result["reason"] == "insufficient_data"

    def test_no_drift(self):
        eng = _engine()
        for _ in range(8):
            eng.record_priority(
                "INC",
                assigned_priority=PriorityLevel.P1_HIGH,
                computed_priority=PriorityLevel.P1_HIGH,
            )
        result = eng.detect_priority_drift()
        assert "drift_detected" in result

    def test_drift_detected(self):
        eng = _engine()
        # First half: accurate
        for _ in range(8):
            eng.record_priority(
                "INC",
                assigned_priority=PriorityLevel.P1_HIGH,
                computed_priority=PriorityLevel.P1_HIGH,
            )
        # Second half: all misranked
        for _ in range(8):
            eng.record_priority(
                "INC",
                assigned_priority=PriorityLevel.P0_CRITICAL,
                computed_priority=PriorityLevel.P3_LOW,
            )
        result = eng.detect_priority_drift()
        assert result["drift_detected"] is True
        assert result["total_records"] == 16


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert isinstance(report, PriorityRankerReport)
        assert report.total_records == 0
        assert report.recommendations

    def test_with_data(self):
        eng = _engine()
        eng.add_factor("user-impact", factor_type=PriorityFactor.USER_IMPACT)
        eng.record_priority(
            "INC-A",
            assigned_priority=PriorityLevel.P0_CRITICAL,
            computed_priority=PriorityLevel.P0_CRITICAL,
        )
        eng.record_priority(
            "INC-B",
            assigned_priority=PriorityLevel.P1_HIGH,
            computed_priority=PriorityLevel.P2_MEDIUM,
        )
        report = eng.generate_report()
        assert report.total_records == 2
        assert report.total_factors == 1
        assert report.misranked_count == 1
        assert report.by_assigned_priority


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears_records_and_factors(self):
        eng = _engine()
        eng.record_priority("INC-A")
        eng.add_factor("factor-a")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._factors) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_factors"] == 0
        assert stats["accuracy_pct"] == 100.0

    def test_populated(self):
        eng = _engine(min_accuracy_pct=85.0)
        eng.record_priority("INC-A", is_misranked=True)
        eng.record_priority("INC-B")
        eng.add_factor("sla-risk", factor_type=PriorityFactor.SLA_RISK)
        stats = eng.get_stats()
        assert stats["total_records"] == 2
        assert stats["total_factors"] == 1
        assert stats["misranked_count"] == 1
        assert stats["min_accuracy_pct"] == 85.0
        assert "method_distribution" in stats
