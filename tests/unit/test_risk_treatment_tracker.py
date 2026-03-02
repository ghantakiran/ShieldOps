"""Tests for shieldops.compliance.risk_treatment_tracker — RiskTreatmentTracker."""

from __future__ import annotations

from shieldops.compliance.risk_treatment_tracker import (
    ResidualRiskLevel,
    RiskTreatmentTracker,
    TreatmentAnalysis,
    TreatmentRecord,
    TreatmentReport,
    TreatmentStatus,
    TreatmentStrategy,
)


def _engine(**kw) -> RiskTreatmentTracker:
    return RiskTreatmentTracker(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_treatmentstrategy_mitigate(self):
        assert TreatmentStrategy.MITIGATE == "mitigate"

    def test_treatmentstrategy_accept(self):
        assert TreatmentStrategy.ACCEPT == "accept"

    def test_treatmentstrategy_transfer(self):
        assert TreatmentStrategy.TRANSFER == "transfer"

    def test_treatmentstrategy_avoid(self):
        assert TreatmentStrategy.AVOID == "avoid"

    def test_treatmentstrategy_share(self):
        assert TreatmentStrategy.SHARE == "share"

    def test_treatmentstatus_implemented(self):
        assert TreatmentStatus.IMPLEMENTED == "implemented"

    def test_treatmentstatus_in_progress(self):
        assert TreatmentStatus.IN_PROGRESS == "in_progress"

    def test_treatmentstatus_planned(self):
        assert TreatmentStatus.PLANNED == "planned"

    def test_treatmentstatus_deferred(self):
        assert TreatmentStatus.DEFERRED == "deferred"

    def test_treatmentstatus_rejected(self):
        assert TreatmentStatus.REJECTED == "rejected"

    def test_residualrisklevel_critical(self):
        assert ResidualRiskLevel.CRITICAL == "critical"

    def test_residualrisklevel_high(self):
        assert ResidualRiskLevel.HIGH == "high"

    def test_residualrisklevel_medium(self):
        assert ResidualRiskLevel.MEDIUM == "medium"

    def test_residualrisklevel_low(self):
        assert ResidualRiskLevel.LOW == "low"

    def test_residualrisklevel_negligible(self):
        assert ResidualRiskLevel.NEGLIGIBLE == "negligible"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_treatmentrecord_defaults(self):
        r = TreatmentRecord()
        assert r.id
        assert r.risk_name == ""
        assert r.residual_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_treatmentanalysis_defaults(self):
        c = TreatmentAnalysis()
        assert c.id
        assert c.risk_name == ""
        assert c.analysis_score == 0.0
        assert c.threshold == 0.0
        assert c.breached == 0.0
        assert c.description == ""
        assert c.created_at > 0

    def test_treatmentreport_defaults(self):
        r = TreatmentReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.high_residual_count == 0
        assert r.avg_residual_score == 0
        assert r.by_strategy == {}
        assert r.by_status == {}
        assert r.by_risk_level == {}
        assert r.top_high_residual == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_treatment
# ---------------------------------------------------------------------------


class TestRecordTreatment:
    def test_basic(self):
        eng = _engine()
        r = eng.record_treatment(
            risk_name="test-item",
            treatment_strategy=TreatmentStrategy.ACCEPT,
            residual_score=92.0,
            service="auth-svc",
            team="security",
        )
        assert r.risk_name == "test-item"
        assert r.residual_score == 92.0
        assert r.service == "auth-svc"
        assert r.team == "security"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_treatment(risk_name=f"ITEM-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_treatment
# ---------------------------------------------------------------------------


class TestGetTreatment:
    def test_found(self):
        eng = _engine()
        r = eng.record_treatment(risk_name="test-item")
        result = eng.get_treatment(r.id)
        assert result is not None
        assert result.risk_name == "test-item"

    def test_not_found(self):
        eng = _engine()
        assert eng.get_treatment("nonexistent") is None


# ---------------------------------------------------------------------------
# list_treatments
# ---------------------------------------------------------------------------


class TestListTreatments:
    def test_list_all(self):
        eng = _engine()
        eng.record_treatment(risk_name="ITEM-001")
        eng.record_treatment(risk_name="ITEM-002")
        assert len(eng.list_treatments()) == 2

    def test_filter_by_treatment_strategy(self):
        eng = _engine()
        eng.record_treatment(risk_name="ITEM-001", treatment_strategy=TreatmentStrategy.MITIGATE)
        eng.record_treatment(risk_name="ITEM-002", treatment_strategy=TreatmentStrategy.ACCEPT)
        results = eng.list_treatments(treatment_strategy=TreatmentStrategy.MITIGATE)
        assert len(results) == 1

    def test_filter_by_treatment_status(self):
        eng = _engine()
        eng.record_treatment(risk_name="ITEM-001", treatment_status=TreatmentStatus.IMPLEMENTED)
        eng.record_treatment(risk_name="ITEM-002", treatment_status=TreatmentStatus.IN_PROGRESS)
        results = eng.list_treatments(treatment_status=TreatmentStatus.IMPLEMENTED)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_treatment(risk_name="ITEM-001", team="security")
        eng.record_treatment(risk_name="ITEM-002", team="platform")
        results = eng.list_treatments(team="security")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_treatment(risk_name=f"ITEM-{i}")
        assert len(eng.list_treatments(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            risk_name="test-item",
            analysis_score=88.5,
            threshold=80.0,
            breached=True,
            description="test description",
        )
        assert a.risk_name == "test-item"
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(risk_name=f"ITEM-{i}")
        assert len(eng._analyses) == 2


# ---------------------------------------------------------------------------
# analyze_treatment_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_treatment(
            risk_name="ITEM-001", treatment_strategy=TreatmentStrategy.MITIGATE, residual_score=90.0
        )
        eng.record_treatment(
            risk_name="ITEM-002", treatment_strategy=TreatmentStrategy.MITIGATE, residual_score=70.0
        )
        result = eng.analyze_treatment_distribution()
        assert "mitigate" in result
        assert result["mitigate"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_treatment_distribution() == {}


# ---------------------------------------------------------------------------
# identify_high_residual_treatments
# ---------------------------------------------------------------------------


class TestIdentifyProblems:
    def test_detects_threshold(self):
        eng = _engine(residual_risk_threshold=50.0)
        eng.record_treatment(risk_name="ITEM-001", residual_score=90.0)
        eng.record_treatment(risk_name="ITEM-002", residual_score=40.0)
        results = eng.identify_high_residual_treatments()
        assert len(results) == 1
        assert results[0]["risk_name"] == "ITEM-001"

    def test_sorted_descending(self):
        eng = _engine(residual_risk_threshold=50.0)
        eng.record_treatment(risk_name="ITEM-001", residual_score=80.0)
        eng.record_treatment(risk_name="ITEM-002", residual_score=95.0)
        results = eng.identify_high_residual_treatments()
        assert len(results) == 2
        assert results[0]["residual_score"] == 95.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_high_residual_treatments() == []


# ---------------------------------------------------------------------------
# rank_by_residual
# ---------------------------------------------------------------------------


class TestRankByScore:
    def test_sorted(self):
        eng = _engine()
        eng.record_treatment(risk_name="ITEM-001", service="auth-svc", residual_score=90.0)
        eng.record_treatment(risk_name="ITEM-002", service="api-gw", residual_score=50.0)
        results = eng.rank_by_residual()
        assert len(results) == 2
        assert results[0]["service"] == "auth-svc"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_residual() == []


# ---------------------------------------------------------------------------
# detect_treatment_trends
# ---------------------------------------------------------------------------


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(risk_name="ITEM-001", analysis_score=50.0)
        result = eng.detect_treatment_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(risk_name="ITEM-001", analysis_score=20.0)
        eng.add_analysis(risk_name="ITEM-002", analysis_score=20.0)
        eng.add_analysis(risk_name="ITEM-003", analysis_score=80.0)
        eng.add_analysis(risk_name="ITEM-004", analysis_score=80.0)
        result = eng.detect_treatment_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_treatment_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(residual_risk_threshold=50.0)
        eng.record_treatment(risk_name="test-item", residual_score=90.0)
        report = eng.generate_report()
        assert isinstance(report, TreatmentReport)
        assert report.total_records == 1
        assert report.high_residual_count == 1
        assert len(report.top_high_residual) == 1
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
        eng.record_treatment(risk_name="ITEM-001")
        eng.add_analysis(risk_name="ITEM-001")
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

    def test_populated(self):
        eng = _engine()
        eng.record_treatment(
            risk_name="ITEM-001",
            treatment_strategy=TreatmentStrategy.MITIGATE,
            service="auth-svc",
            team="security",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
