"""Tests for shieldops.compliance.regulation_tracker — RegulatoryChangeTracker."""

from __future__ import annotations

from shieldops.compliance.regulation_tracker import (
    ChangeImpact,
    ComplianceAction,
    ImpactAnalysis,
    RegulationType,
    RegulatoryChangeReport,
    RegulatoryChangeTracker,
    RegulatoryRecord,
)


def _engine(**kw) -> RegulatoryChangeTracker:
    return RegulatoryChangeTracker(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_regulation_type_gdpr(self):
        assert RegulationType.GDPR == "gdpr"

    def test_regulation_type_soc2(self):
        assert RegulationType.SOC2 == "soc2"

    def test_regulation_type_hipaa(self):
        assert RegulationType.HIPAA == "hipaa"

    def test_regulation_type_pci_dss(self):
        assert RegulationType.PCI_DSS == "pci_dss"

    def test_regulation_type_iso27001(self):
        assert RegulationType.ISO27001 == "iso27001"

    def test_change_impact_critical(self):
        assert ChangeImpact.CRITICAL == "critical"

    def test_change_impact_high(self):
        assert ChangeImpact.HIGH == "high"

    def test_change_impact_moderate(self):
        assert ChangeImpact.MODERATE == "moderate"

    def test_change_impact_low(self):
        assert ChangeImpact.LOW == "low"

    def test_change_impact_informational(self):
        assert ChangeImpact.INFORMATIONAL == "informational"

    def test_compliance_action_policy_update(self):
        assert ComplianceAction.POLICY_UPDATE == "policy_update"

    def test_compliance_action_control_addition(self):
        assert ComplianceAction.CONTROL_ADDITION == "control_addition"

    def test_compliance_action_process_change(self):
        assert ComplianceAction.PROCESS_CHANGE == "process_change"

    def test_compliance_action_training_required(self):
        assert ComplianceAction.TRAINING_REQUIRED == "training_required"

    def test_compliance_action_no_action(self):
        assert ComplianceAction.NO_ACTION == "no_action"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_regulatory_record_defaults(self):
        r = RegulatoryRecord()
        assert r.id
        assert r.regulation_id == ""
        assert r.regulation_type == RegulationType.GDPR
        assert r.change_impact == ChangeImpact.INFORMATIONAL
        assert r.compliance_action == ComplianceAction.NO_ACTION
        assert r.impact_score == 0.0
        assert r.team == ""
        assert r.created_at > 0

    def test_impact_analysis_defaults(self):
        a = ImpactAnalysis()
        assert a.id
        assert a.analysis_pattern == ""
        assert a.regulation_type == RegulationType.GDPR
        assert a.urgency_score == 0.0
        assert a.affected_controls == 0
        assert a.description == ""
        assert a.created_at > 0

    def test_regulatory_change_report_defaults(self):
        r = RegulatoryChangeReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.high_impact_changes == 0
        assert r.avg_impact_score == 0.0
        assert r.by_type == {}
        assert r.by_impact == {}
        assert r.by_action == {}
        assert r.urgent == []
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
            regulation_id="REG-001",
            regulation_type=RegulationType.SOC2,
            change_impact=ChangeImpact.HIGH,
            compliance_action=ComplianceAction.POLICY_UPDATE,
            impact_score=85.0,
            team="compliance",
        )
        assert r.regulation_id == "REG-001"
        assert r.regulation_type == RegulationType.SOC2
        assert r.change_impact == ChangeImpact.HIGH
        assert r.compliance_action == ComplianceAction.POLICY_UPDATE
        assert r.impact_score == 85.0
        assert r.team == "compliance"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_change(regulation_id=f"REG-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_change
# ---------------------------------------------------------------------------


class TestGetChange:
    def test_found(self):
        eng = _engine()
        r = eng.record_change(
            regulation_id="REG-001",
            regulation_type=RegulationType.HIPAA,
        )
        result = eng.get_change(r.id)
        assert result is not None
        assert result.regulation_type == RegulationType.HIPAA

    def test_not_found(self):
        eng = _engine()
        assert eng.get_change("nonexistent") is None


# ---------------------------------------------------------------------------
# list_changes
# ---------------------------------------------------------------------------


class TestListChanges:
    def test_list_all(self):
        eng = _engine()
        eng.record_change(regulation_id="REG-001")
        eng.record_change(regulation_id="REG-002")
        assert len(eng.list_changes()) == 2

    def test_filter_by_regulation_type(self):
        eng = _engine()
        eng.record_change(
            regulation_id="REG-001",
            regulation_type=RegulationType.GDPR,
        )
        eng.record_change(
            regulation_id="REG-002",
            regulation_type=RegulationType.PCI_DSS,
        )
        results = eng.list_changes(regulation_type=RegulationType.GDPR)
        assert len(results) == 1

    def test_filter_by_change_impact(self):
        eng = _engine()
        eng.record_change(
            regulation_id="REG-001",
            change_impact=ChangeImpact.CRITICAL,
        )
        eng.record_change(
            regulation_id="REG-002",
            change_impact=ChangeImpact.LOW,
        )
        results = eng.list_changes(change_impact=ChangeImpact.CRITICAL)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_change(regulation_id="REG-001", team="compliance")
        eng.record_change(regulation_id="REG-002", team="security")
        results = eng.list_changes(team="compliance")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_change(regulation_id=f"REG-{i}")
        assert len(eng.list_changes(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            analysis_pattern="gdpr-update-*",
            regulation_type=RegulationType.HIPAA,
            urgency_score=9.0,
            affected_controls=5,
            description="HIPAA update analysis",
        )
        assert a.analysis_pattern == "gdpr-update-*"
        assert a.regulation_type == RegulationType.HIPAA
        assert a.urgency_score == 9.0
        assert a.affected_controls == 5

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(analysis_pattern=f"pat-{i}")
        assert len(eng._analyses) == 2


# ---------------------------------------------------------------------------
# analyze_regulatory_impact
# ---------------------------------------------------------------------------


class TestAnalyzeRegulatoryImpact:
    def test_with_data(self):
        eng = _engine()
        eng.record_change(
            regulation_id="REG-001",
            regulation_type=RegulationType.GDPR,
            impact_score=80.0,
        )
        eng.record_change(
            regulation_id="REG-002",
            regulation_type=RegulationType.GDPR,
            impact_score=60.0,
        )
        result = eng.analyze_regulatory_impact()
        assert "gdpr" in result
        assert result["gdpr"]["count"] == 2
        assert result["gdpr"]["avg_impact_score"] == 70.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_regulatory_impact() == {}


# ---------------------------------------------------------------------------
# identify_high_impact_changes
# ---------------------------------------------------------------------------


class TestIdentifyHighImpactChanges:
    def test_detects_high_impact(self):
        eng = _engine(max_impact_score=75.0)
        eng.record_change(
            regulation_id="REG-001",
            impact_score=80.0,
        )
        eng.record_change(
            regulation_id="REG-002",
            impact_score=50.0,
        )
        results = eng.identify_high_impact_changes()
        assert len(results) == 1
        assert results[0]["regulation_id"] == "REG-001"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_high_impact_changes() == []


# ---------------------------------------------------------------------------
# rank_by_urgency
# ---------------------------------------------------------------------------


class TestRankByUrgency:
    def test_ranked_descending(self):
        eng = _engine()
        eng.record_change(regulation_id="REG-001", team="compliance", impact_score=80.0)
        eng.record_change(regulation_id="REG-002", team="compliance", impact_score=70.0)
        eng.record_change(regulation_id="REG-003", team="security", impact_score=50.0)
        results = eng.rank_by_urgency()
        assert len(results) == 2
        assert results[0]["team"] == "compliance"
        assert results[0]["total_impact"] == 150.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_urgency() == []


# ---------------------------------------------------------------------------
# detect_regulatory_trends
# ---------------------------------------------------------------------------


class TestDetectRegulatoryTrends:
    def test_stable(self):
        eng = _engine()
        for score in [50.0, 50.0, 50.0, 50.0]:
            eng.record_change(regulation_id="REG", impact_score=score)
        result = eng.detect_regulatory_trends()
        assert result["trend"] == "stable"

    def test_increasing(self):
        eng = _engine()
        for score in [30.0, 30.0, 80.0, 80.0]:
            eng.record_change(regulation_id="REG", impact_score=score)
        result = eng.detect_regulatory_trends()
        assert result["trend"] == "increasing"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_regulatory_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(max_impact_score=75.0)
        eng.record_change(
            regulation_id="REG-001",
            regulation_type=RegulationType.GDPR,
            change_impact=ChangeImpact.HIGH,
            impact_score=80.0,
            team="compliance",
        )
        report = eng.generate_report()
        assert isinstance(report, RegulatoryChangeReport)
        assert report.total_records == 1
        assert report.avg_impact_score == 80.0
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
        eng.record_change(regulation_id="REG-001")
        eng.add_analysis(analysis_pattern="a1")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_analyses"] == 0
        assert stats["type_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_change(
            regulation_id="REG-001",
            regulation_type=RegulationType.SOC2,
            team="compliance",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_regulations"] == 1
        assert "soc2" in stats["type_distribution"]
