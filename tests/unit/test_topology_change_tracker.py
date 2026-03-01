"""Tests for shieldops.topology.topology_change_tracker — TopologyChangeTracker."""

from __future__ import annotations

from shieldops.topology.topology_change_tracker import (
    ChangeImpact,
    ChangeImpactAssessment,
    ChangeSource,
    ChangeType,
    TopologyChangeRecord,
    TopologyChangeReport,
    TopologyChangeTracker,
)


def _engine(**kw) -> TopologyChangeTracker:
    return TopologyChangeTracker(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_type_node_added(self):
        assert ChangeType.NODE_ADDED == "node_added"

    def test_type_node_removed(self):
        assert ChangeType.NODE_REMOVED == "node_removed"

    def test_type_edge_modified(self):
        assert ChangeType.EDGE_MODIFIED == "edge_modified"

    def test_type_weight_changed(self):
        assert ChangeType.WEIGHT_CHANGED == "weight_changed"

    def test_type_dependency_shifted(self):
        assert ChangeType.DEPENDENCY_SHIFTED == "dependency_shifted"

    def test_impact_critical(self):
        assert ChangeImpact.CRITICAL == "critical"

    def test_impact_high(self):
        assert ChangeImpact.HIGH == "high"

    def test_impact_moderate(self):
        assert ChangeImpact.MODERATE == "moderate"

    def test_impact_low(self):
        assert ChangeImpact.LOW == "low"

    def test_impact_none(self):
        assert ChangeImpact.NONE == "none"

    def test_source_deployment(self):
        assert ChangeSource.DEPLOYMENT == "deployment"

    def test_source_scaling(self):
        assert ChangeSource.SCALING == "scaling"

    def test_source_failover(self):
        assert ChangeSource.FAILOVER == "failover"

    def test_source_configuration(self):
        assert ChangeSource.CONFIGURATION == "configuration"

    def test_source_manual(self):
        assert ChangeSource.MANUAL == "manual"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_topology_change_record_defaults(self):
        r = TopologyChangeRecord()
        assert r.id
        assert r.change_id == ""
        assert r.change_type == ChangeType.NODE_ADDED
        assert r.change_impact == ChangeImpact.NONE
        assert r.change_source == ChangeSource.DEPLOYMENT
        assert r.impact_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_change_impact_assessment_defaults(self):
        a = ChangeImpactAssessment()
        assert a.id
        assert a.change_id == ""
        assert a.change_type == ChangeType.NODE_ADDED
        assert a.assessment_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = TopologyChangeReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_assessments == 0
        assert r.high_impact_changes == 0
        assert r.avg_impact_score == 0.0
        assert r.by_type == {}
        assert r.by_impact == {}
        assert r.by_source == {}
        assert r.top_impactful == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_change
# ---------------------------------------------------------------------------


class TestRecordChange:
    def test_basic(self):
        eng = _engine()
        r = eng.record_change(
            change_id="CHG-001",
            change_type=ChangeType.NODE_REMOVED,
            change_impact=ChangeImpact.CRITICAL,
            change_source=ChangeSource.FAILOVER,
            impact_score=95.0,
            service="payment-svc",
            team="sre",
        )
        assert r.change_id == "CHG-001"
        assert r.change_type == ChangeType.NODE_REMOVED
        assert r.change_impact == ChangeImpact.CRITICAL
        assert r.change_source == ChangeSource.FAILOVER
        assert r.impact_score == 95.0
        assert r.service == "payment-svc"
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_change(change_id=f"CHG-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_change
# ---------------------------------------------------------------------------


class TestGetChange:
    def test_found(self):
        eng = _engine()
        r = eng.record_change(
            change_id="CHG-001",
            change_impact=ChangeImpact.HIGH,
        )
        result = eng.get_change(r.id)
        assert result is not None
        assert result.change_impact == ChangeImpact.HIGH

    def test_not_found(self):
        eng = _engine()
        assert eng.get_change("nonexistent") is None


# ---------------------------------------------------------------------------
# list_changes
# ---------------------------------------------------------------------------


class TestListChanges:
    def test_list_all(self):
        eng = _engine()
        eng.record_change(change_id="CHG-001")
        eng.record_change(change_id="CHG-002")
        assert len(eng.list_changes()) == 2

    def test_filter_by_type(self):
        eng = _engine()
        eng.record_change(
            change_id="CHG-001",
            change_type=ChangeType.NODE_ADDED,
        )
        eng.record_change(
            change_id="CHG-002",
            change_type=ChangeType.EDGE_MODIFIED,
        )
        results = eng.list_changes(change_type=ChangeType.NODE_ADDED)
        assert len(results) == 1

    def test_filter_by_impact(self):
        eng = _engine()
        eng.record_change(
            change_id="CHG-001",
            change_impact=ChangeImpact.CRITICAL,
        )
        eng.record_change(
            change_id="CHG-002",
            change_impact=ChangeImpact.LOW,
        )
        results = eng.list_changes(change_impact=ChangeImpact.CRITICAL)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_change(change_id="CHG-001", team="sre")
        eng.record_change(change_id="CHG-002", team="platform")
        results = eng.list_changes(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_change(change_id=f"CHG-{i}")
        assert len(eng.list_changes(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_assessment
# ---------------------------------------------------------------------------


class TestAddAssessment:
    def test_basic(self):
        eng = _engine()
        a = eng.add_assessment(
            change_id="CHG-001",
            change_type=ChangeType.EDGE_MODIFIED,
            assessment_score=72.0,
            threshold=80.0,
            breached=True,
            description="Below threshold",
        )
        assert a.change_id == "CHG-001"
        assert a.change_type == ChangeType.EDGE_MODIFIED
        assert a.assessment_score == 72.0
        assert a.threshold == 80.0
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_assessment(change_id=f"CHG-{i}")
        assert len(eng._assessments) == 2


# ---------------------------------------------------------------------------
# analyze_change_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeChangeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_change(
            change_id="CHG-001",
            change_type=ChangeType.NODE_ADDED,
            impact_score=50.0,
        )
        eng.record_change(
            change_id="CHG-002",
            change_type=ChangeType.NODE_ADDED,
            impact_score=70.0,
        )
        result = eng.analyze_change_distribution()
        assert "node_added" in result
        assert result["node_added"]["count"] == 2
        assert result["node_added"]["avg_impact_score"] == 60.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_change_distribution() == {}


# ---------------------------------------------------------------------------
# identify_high_impact_changes
# ---------------------------------------------------------------------------


class TestIdentifyHighImpactChanges:
    def test_detects_high_impact(self):
        eng = _engine()
        eng.record_change(
            change_id="CHG-001",
            change_impact=ChangeImpact.CRITICAL,
            impact_score=90.0,
        )
        eng.record_change(
            change_id="CHG-002",
            change_impact=ChangeImpact.LOW,
            impact_score=10.0,
        )
        results = eng.identify_high_impact_changes()
        assert len(results) == 1
        assert results[0]["change_id"] == "CHG-001"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_high_impact_changes() == []


# ---------------------------------------------------------------------------
# rank_by_impact_score
# ---------------------------------------------------------------------------


class TestRankByImpactScore:
    def test_ranked_descending(self):
        eng = _engine()
        eng.record_change(
            change_id="CHG-001",
            service="high-svc",
            impact_score=90.0,
        )
        eng.record_change(
            change_id="CHG-002",
            service="low-svc",
            impact_score=10.0,
        )
        results = eng.rank_by_impact_score()
        assert len(results) == 2
        assert results[0]["service"] == "high-svc"
        assert results[0]["avg_impact_score"] == 90.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_impact_score() == []


# ---------------------------------------------------------------------------
# detect_change_trends
# ---------------------------------------------------------------------------


class TestDetectChangeTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_assessment(change_id="CHG-001", assessment_score=50.0)
        result = eng.detect_change_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_assessment(change_id="CHG-001", assessment_score=30.0)
        eng.add_assessment(change_id="CHG-002", assessment_score=30.0)
        eng.add_assessment(change_id="CHG-003", assessment_score=80.0)
        eng.add_assessment(change_id="CHG-004", assessment_score=80.0)
        result = eng.detect_change_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_change_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_change(
            change_id="CHG-001",
            change_type=ChangeType.NODE_REMOVED,
            change_impact=ChangeImpact.CRITICAL,
            change_source=ChangeSource.FAILOVER,
            impact_score=95.0,
            service="payment-svc",
        )
        report = eng.generate_report()
        assert isinstance(report, TopologyChangeReport)
        assert report.total_records == 1
        assert report.high_impact_changes == 1
        assert len(report.top_impactful) == 1
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
        eng.record_change(change_id="CHG-001")
        eng.add_assessment(change_id="CHG-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._assessments) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_assessments"] == 0
        assert stats["type_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_change(
            change_id="CHG-001",
            change_type=ChangeType.NODE_ADDED,
            team="sre",
            service="api-svc",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "node_added" in stats["type_distribution"]
