"""Tests for shieldops.compliance.control_effectiveness — ControlEffectivenessTracker."""

from __future__ import annotations

from shieldops.compliance.control_effectiveness import (
    ControlDomain,
    ControlEffectivenessReport,
    ControlEffectivenessTracker,
    ControlRecord,
    ControlType,
    EffectivenessLevel,
    EffectivenessTest,
)


def _engine(**kw) -> ControlEffectivenessTracker:
    return ControlEffectivenessTracker(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_control_type_preventive(self):
        assert ControlType.PREVENTIVE == "preventive"

    def test_control_type_detective(self):
        assert ControlType.DETECTIVE == "detective"

    def test_control_type_corrective(self):
        assert ControlType.CORRECTIVE == "corrective"

    def test_control_type_compensating(self):
        assert ControlType.COMPENSATING == "compensating"

    def test_control_type_directive(self):
        assert ControlType.DIRECTIVE == "directive"

    def test_effectiveness_level_highly_effective(self):
        assert EffectivenessLevel.HIGHLY_EFFECTIVE == "highly_effective"

    def test_effectiveness_level_effective(self):
        assert EffectivenessLevel.EFFECTIVE == "effective"

    def test_effectiveness_level_partially_effective(self):
        assert EffectivenessLevel.PARTIALLY_EFFECTIVE == "partially_effective"

    def test_effectiveness_level_ineffective(self):
        assert EffectivenessLevel.INEFFECTIVE == "ineffective"

    def test_effectiveness_level_not_tested(self):
        assert EffectivenessLevel.NOT_TESTED == "not_tested"

    def test_control_domain_access_management(self):
        assert ControlDomain.ACCESS_MANAGEMENT == "access_management"

    def test_control_domain_data_protection(self):
        assert ControlDomain.DATA_PROTECTION == "data_protection"

    def test_control_domain_change_control(self):
        assert ControlDomain.CHANGE_CONTROL == "change_control"

    def test_control_domain_incident_response(self):
        assert ControlDomain.INCIDENT_RESPONSE == "incident_response"

    def test_control_domain_monitoring(self):
        assert ControlDomain.MONITORING == "monitoring"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_control_record_defaults(self):
        r = ControlRecord()
        assert r.id
        assert r.control_id == ""
        assert r.control_type == ControlType.PREVENTIVE
        assert r.effectiveness_level == EffectivenessLevel.NOT_TESTED
        assert r.control_domain == ControlDomain.ACCESS_MANAGEMENT
        assert r.effectiveness_pct == 0.0
        assert r.team == ""
        assert r.created_at > 0

    def test_effectiveness_test_defaults(self):
        t = EffectivenessTest()
        assert t.id
        assert t.test_name == ""
        assert t.control_type == ControlType.PREVENTIVE
        assert t.test_score == 0.0
        assert t.controls_tested == 0
        assert t.description == ""
        assert t.created_at > 0

    def test_control_effectiveness_report_defaults(self):
        r = ControlEffectivenessReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_tests == 0
        assert r.effective_controls == 0
        assert r.avg_effectiveness_pct == 0.0
        assert r.by_type == {}
        assert r.by_level == {}
        assert r.by_domain == {}
        assert r.weak_controls == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_control
# ---------------------------------------------------------------------------


class TestRecordControl:
    def test_basic(self):
        eng = _engine()
        r = eng.record_control(
            control_id="CTL-001",
            control_type=ControlType.DETECTIVE,
            effectiveness_level=EffectivenessLevel.HIGHLY_EFFECTIVE,
            control_domain=ControlDomain.DATA_PROTECTION,
            effectiveness_pct=95.0,
            team="security",
        )
        assert r.control_id == "CTL-001"
        assert r.control_type == ControlType.DETECTIVE
        assert r.effectiveness_level == EffectivenessLevel.HIGHLY_EFFECTIVE
        assert r.control_domain == ControlDomain.DATA_PROTECTION
        assert r.effectiveness_pct == 95.0
        assert r.team == "security"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_control(control_id=f"CTL-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_control
# ---------------------------------------------------------------------------


class TestGetControl:
    def test_found(self):
        eng = _engine()
        r = eng.record_control(
            control_id="CTL-001",
            control_type=ControlType.CORRECTIVE,
        )
        result = eng.get_control(r.id)
        assert result is not None
        assert result.control_type == ControlType.CORRECTIVE

    def test_not_found(self):
        eng = _engine()
        assert eng.get_control("nonexistent") is None


# ---------------------------------------------------------------------------
# list_controls
# ---------------------------------------------------------------------------


class TestListControls:
    def test_list_all(self):
        eng = _engine()
        eng.record_control(control_id="CTL-001")
        eng.record_control(control_id="CTL-002")
        assert len(eng.list_controls()) == 2

    def test_filter_by_control_type(self):
        eng = _engine()
        eng.record_control(
            control_id="CTL-001",
            control_type=ControlType.PREVENTIVE,
        )
        eng.record_control(
            control_id="CTL-002",
            control_type=ControlType.DETECTIVE,
        )
        results = eng.list_controls(control_type=ControlType.PREVENTIVE)
        assert len(results) == 1

    def test_filter_by_effectiveness_level(self):
        eng = _engine()
        eng.record_control(
            control_id="CTL-001",
            effectiveness_level=EffectivenessLevel.HIGHLY_EFFECTIVE,
        )
        eng.record_control(
            control_id="CTL-002",
            effectiveness_level=EffectivenessLevel.INEFFECTIVE,
        )
        results = eng.list_controls(effectiveness_level=EffectivenessLevel.HIGHLY_EFFECTIVE)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_control(control_id="CTL-001", team="security")
        eng.record_control(control_id="CTL-002", team="compliance")
        results = eng.list_controls(team="security")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_control(control_id=f"CTL-{i}")
        assert len(eng.list_controls(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_test
# ---------------------------------------------------------------------------


class TestAddTest:
    def test_basic(self):
        eng = _engine()
        t = eng.add_test(
            test_name="access-control-validation",
            control_type=ControlType.COMPENSATING,
            test_score=8.5,
            controls_tested=3,
            description="Validate compensating access controls",
        )
        assert t.test_name == "access-control-validation"
        assert t.control_type == ControlType.COMPENSATING
        assert t.test_score == 8.5
        assert t.controls_tested == 3

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_test(test_name=f"test-{i}")
        assert len(eng._tests) == 2


# ---------------------------------------------------------------------------
# analyze_control_effectiveness
# ---------------------------------------------------------------------------


class TestAnalyzeControlEffectiveness:
    def test_with_data(self):
        eng = _engine()
        eng.record_control(
            control_id="CTL-001",
            control_type=ControlType.PREVENTIVE,
            effectiveness_pct=90.0,
        )
        eng.record_control(
            control_id="CTL-002",
            control_type=ControlType.PREVENTIVE,
            effectiveness_pct=80.0,
        )
        result = eng.analyze_control_effectiveness()
        assert "preventive" in result
        assert result["preventive"]["count"] == 2
        assert result["preventive"]["avg_effectiveness_pct"] == 85.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_control_effectiveness() == {}


# ---------------------------------------------------------------------------
# identify_weak_controls
# ---------------------------------------------------------------------------


class TestIdentifyWeakControls:
    def test_detects_weak(self):
        eng = _engine(min_effectiveness_pct=80.0)
        eng.record_control(
            control_id="CTL-001",
            effectiveness_pct=50.0,
        )
        eng.record_control(
            control_id="CTL-002",
            effectiveness_pct=95.0,
        )
        results = eng.identify_weak_controls()
        assert len(results) == 1
        assert results[0]["control_id"] == "CTL-001"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_weak_controls() == []


# ---------------------------------------------------------------------------
# rank_by_effectiveness
# ---------------------------------------------------------------------------


class TestRankByEffectiveness:
    def test_ranked_descending(self):
        eng = _engine()
        eng.record_control(control_id="CTL-001", team="security", effectiveness_pct=90.0)
        eng.record_control(control_id="CTL-002", team="security", effectiveness_pct=80.0)
        eng.record_control(control_id="CTL-003", team="compliance", effectiveness_pct=50.0)
        results = eng.rank_by_effectiveness()
        assert len(results) == 2
        assert results[0]["team"] == "security"
        assert results[0]["total_effectiveness"] == 170.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_effectiveness() == []


# ---------------------------------------------------------------------------
# detect_effectiveness_trends
# ---------------------------------------------------------------------------


class TestDetectEffectivenessTrends:
    def test_stable(self):
        eng = _engine()
        for pct in [80.0, 80.0, 80.0, 80.0]:
            eng.record_control(control_id="CTL", effectiveness_pct=pct)
        result = eng.detect_effectiveness_trends()
        assert result["trend"] == "stable"

    def test_increasing(self):
        eng = _engine()
        for pct in [50.0, 50.0, 90.0, 90.0]:
            eng.record_control(control_id="CTL", effectiveness_pct=pct)
        result = eng.detect_effectiveness_trends()
        assert result["trend"] == "increasing"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_effectiveness_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(min_effectiveness_pct=80.0)
        eng.record_control(
            control_id="CTL-001",
            control_type=ControlType.PREVENTIVE,
            effectiveness_level=EffectivenessLevel.PARTIALLY_EFFECTIVE,
            effectiveness_pct=50.0,
            team="security",
        )
        report = eng.generate_report()
        assert isinstance(report, ControlEffectivenessReport)
        assert report.total_records == 1
        assert report.avg_effectiveness_pct == 50.0
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
        eng.record_control(control_id="CTL-001")
        eng.add_test(test_name="t1")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._tests) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_tests"] == 0
        assert stats["type_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_control(
            control_id="CTL-001",
            control_type=ControlType.DETECTIVE,
            team="security",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_controls"] == 1
        assert "detective" in stats["type_distribution"]
