"""Tests for shieldops.security.exposure_severity_scorer — ExposureSeverityScorer."""

from __future__ import annotations

from shieldops.security.exposure_severity_scorer import (
    ExposureSeverityAnalysis,
    ExposureSeverityRecord,
    ExposureSeverityReport,
    ExposureSeverityScorer,
    ExposureType,
    ScoringFactor,
    SeverityRating,
)


def _engine(**kw) -> ExposureSeverityScorer:
    return ExposureSeverityScorer(**kw)


class TestEnums:
    def test_exposuretype_val1(self):
        assert ExposureType.OPEN_PORT == "open_port"

    def test_exposuretype_val2(self):
        assert ExposureType.MISCONFIGURATION == "misconfiguration"

    def test_exposuretype_val3(self):
        assert ExposureType.WEAK_CREDENTIAL == "weak_credential"  # noqa: S105

    def test_exposuretype_val4(self):
        assert ExposureType.UNPATCHED_CVE == "unpatched_cve"

    def test_exposuretype_val5(self):
        assert ExposureType.DATA_LEAK == "data_leak"

    def test_severityrating_val1(self):
        assert SeverityRating.CRITICAL == "critical"

    def test_severityrating_val2(self):
        assert SeverityRating.HIGH == "high"

    def test_severityrating_val3(self):
        assert SeverityRating.MEDIUM == "medium"

    def test_severityrating_val4(self):
        assert SeverityRating.LOW == "low"

    def test_severityrating_val5(self):
        assert SeverityRating.INFORMATIONAL == "informational"

    def test_scoringfactor_val1(self):
        assert ScoringFactor.EXPLOITABILITY == "exploitability"

    def test_scoringfactor_val2(self):
        assert ScoringFactor.IMPACT == "impact"

    def test_scoringfactor_val3(self):
        assert ScoringFactor.ASSET_VALUE == "asset_value"

    def test_scoringfactor_val4(self):
        assert ScoringFactor.THREAT_CONTEXT == "threat_context"

    def test_scoringfactor_val5(self):
        assert ScoringFactor.REMEDIATION_COST == "remediation_cost"


class TestModels:
    def test_record_defaults(self):
        r = ExposureSeverityRecord()
        assert r.id
        assert r.exposure_name == ""

    def test_analysis_defaults(self):
        a = ExposureSeverityAnalysis()
        assert a.id
        assert a.analysis_score == 0.0
        assert a.breached is False

    def test_report_defaults(self):
        r = ExposureSeverityReport()
        assert r.total_records == 0
        assert r.recommendations == []


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_exposure(
            exposure_name="test",
            exposure_type=ExposureType.MISCONFIGURATION,
            risk_score=92.0,
            service="auth",
            team="sec",
        )
        assert r.exposure_name == "test"
        assert r.risk_score == 92.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_exposure(exposure_name=f"t-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_exposure(exposure_name="test")
        assert eng.get_exposure(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_exposure("nope") is None


class TestList:
    def test_list_all(self):
        eng = _engine()
        eng.record_exposure(exposure_name="a")
        eng.record_exposure(exposure_name="b")
        assert len(eng.list_exposures()) == 2

    def test_filter_by_enum1(self):
        eng = _engine()
        eng.record_exposure(exposure_name="a", exposure_type=ExposureType.OPEN_PORT)
        eng.record_exposure(exposure_name="b", exposure_type=ExposureType.MISCONFIGURATION)
        assert len(eng.list_exposures(exposure_type=ExposureType.OPEN_PORT)) == 1

    def test_filter_by_enum2(self):
        eng = _engine()
        eng.record_exposure(exposure_name="a", severity_rating=SeverityRating.CRITICAL)
        eng.record_exposure(exposure_name="b", severity_rating=SeverityRating.HIGH)
        assert len(eng.list_exposures(severity_rating=SeverityRating.CRITICAL)) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_exposure(exposure_name="a", team="sec")
        eng.record_exposure(exposure_name="b", team="ops")
        assert len(eng.list_exposures(team="sec")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_exposure(exposure_name=f"t-{i}")
        assert len(eng.list_exposures(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            exposure_name="test", analysis_score=88.5, breached=True, description="gap"
        )
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(exposure_name=f"t-{i}")
        assert len(eng._analyses) == 2


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_exposure(
            exposure_name="a", exposure_type=ExposureType.OPEN_PORT, risk_score=90.0
        )
        eng.record_exposure(
            exposure_name="b", exposure_type=ExposureType.OPEN_PORT, risk_score=70.0
        )
        result = eng.analyze_distribution()
        assert ExposureType.OPEN_PORT.value in result
        assert result[ExposureType.OPEN_PORT.value]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(risk_threshold=80.0)
        eng.record_exposure(exposure_name="a", risk_score=60.0)
        eng.record_exposure(exposure_name="b", risk_score=90.0)
        results = eng.identify_gaps()
        assert len(results) == 1

    def test_sorted_ascending(self):
        eng = _engine(risk_threshold=80.0)
        eng.record_exposure(exposure_name="a", risk_score=50.0)
        eng.record_exposure(exposure_name="b", risk_score=30.0)
        results = eng.identify_gaps()
        assert results[0]["risk_score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_gaps() == []


class TestRankByScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_exposure(exposure_name="a", service="auth", risk_score=90.0)
        eng.record_exposure(exposure_name="b", service="api", risk_score=50.0)
        results = eng.rank_by_score()
        assert results[0]["service"] == "api"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_score() == []


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(exposure_name="t", analysis_score=50.0)
        assert eng.detect_trends()["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(exposure_name="a", analysis_score=20.0)
        eng.add_analysis(exposure_name="b", analysis_score=20.0)
        eng.add_analysis(exposure_name="c", analysis_score=80.0)
        eng.add_analysis(exposure_name="d", analysis_score=80.0)
        assert eng.detect_trends()["trend"] == "improving"

    def test_insufficient_data(self):
        eng = _engine()
        assert eng.detect_trends()["trend"] == "insufficient_data"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(risk_threshold=80.0)
        eng.record_exposure(exposure_name="test", risk_score=50.0)
        report = eng.generate_report()
        assert report.total_records == 1
        assert report.gap_count == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert (
            "healthy" in report.recommendations[0].lower()
            or "within" in report.recommendations[0].lower()
        )


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_exposure(exposure_name="test")
        eng.add_analysis(exposure_name="test")
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
        eng.record_exposure(exposure_name="test", service="auth", team="sec")
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
