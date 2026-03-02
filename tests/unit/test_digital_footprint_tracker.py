"""Tests for shieldops.security.digital_footprint_tracker — DigitalFootprintTracker."""

from __future__ import annotations

from shieldops.security.digital_footprint_tracker import (
    DigitalFootprintTracker,
    FootprintAnalysis,
    FootprintRecord,
    FootprintReport,
    FootprintRisk,
    FootprintType,
    FootprintVisibility,
)


def _engine(**kw) -> DigitalFootprintTracker:
    return DigitalFootprintTracker(**kw)


class TestEnums:
    def test_footprinttype_val1(self):
        assert FootprintType.DOMAIN == "domain"

    def test_footprinttype_val2(self):
        assert FootprintType.SOCIAL_MEDIA == "social_media"

    def test_footprinttype_val3(self):
        assert FootprintType.CODE_REPOSITORY == "code_repository"

    def test_footprinttype_val4(self):
        assert FootprintType.CLOUD_ASSET == "cloud_asset"

    def test_footprinttype_val5(self):
        assert FootprintType.DATA_EXPOSURE == "data_exposure"

    def test_footprintvisibility_val1(self):
        assert FootprintVisibility.PUBLIC == "public"

    def test_footprintvisibility_val2(self):
        assert FootprintVisibility.SEMI_PUBLIC == "semi_public"

    def test_footprintvisibility_val3(self):
        assert FootprintVisibility.RESTRICTED == "restricted"

    def test_footprintvisibility_val4(self):
        assert FootprintVisibility.PRIVATE == "private"

    def test_footprintvisibility_val5(self):
        assert FootprintVisibility.UNKNOWN == "unknown"

    def test_footprintrisk_val1(self):
        assert FootprintRisk.CRITICAL == "critical"

    def test_footprintrisk_val2(self):
        assert FootprintRisk.HIGH == "high"

    def test_footprintrisk_val3(self):
        assert FootprintRisk.MEDIUM == "medium"

    def test_footprintrisk_val4(self):
        assert FootprintRisk.LOW == "low"

    def test_footprintrisk_val5(self):
        assert FootprintRisk.BENIGN == "benign"


class TestModels:
    def test_record_defaults(self):
        r = FootprintRecord()
        assert r.id
        assert r.asset_name == ""

    def test_analysis_defaults(self):
        a = FootprintAnalysis()
        assert a.id
        assert a.analysis_score == 0.0
        assert a.breached is False

    def test_report_defaults(self):
        r = FootprintReport()
        assert r.total_records == 0
        assert r.recommendations == []


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_footprint(
            asset_name="test",
            footprint_type=FootprintType.SOCIAL_MEDIA,
            risk_score=92.0,
            service="auth",
            team="sec",
        )
        assert r.asset_name == "test"
        assert r.risk_score == 92.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_footprint(asset_name=f"t-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_footprint(asset_name="test")
        assert eng.get_footprint(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_footprint("nope") is None


class TestList:
    def test_list_all(self):
        eng = _engine()
        eng.record_footprint(asset_name="a")
        eng.record_footprint(asset_name="b")
        assert len(eng.list_footprints()) == 2

    def test_filter_by_enum1(self):
        eng = _engine()
        eng.record_footprint(asset_name="a", footprint_type=FootprintType.DOMAIN)
        eng.record_footprint(asset_name="b", footprint_type=FootprintType.SOCIAL_MEDIA)
        assert len(eng.list_footprints(footprint_type=FootprintType.DOMAIN)) == 1

    def test_filter_by_enum2(self):
        eng = _engine()
        eng.record_footprint(asset_name="a", footprint_visibility=FootprintVisibility.PUBLIC)
        eng.record_footprint(asset_name="b", footprint_visibility=FootprintVisibility.SEMI_PUBLIC)
        assert len(eng.list_footprints(footprint_visibility=FootprintVisibility.PUBLIC)) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_footprint(asset_name="a", team="sec")
        eng.record_footprint(asset_name="b", team="ops")
        assert len(eng.list_footprints(team="sec")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_footprint(asset_name=f"t-{i}")
        assert len(eng.list_footprints(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            asset_name="test", analysis_score=88.5, breached=True, description="gap"
        )
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(asset_name=f"t-{i}")
        assert len(eng._analyses) == 2


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_footprint(asset_name="a", footprint_type=FootprintType.DOMAIN, risk_score=90.0)
        eng.record_footprint(asset_name="b", footprint_type=FootprintType.DOMAIN, risk_score=70.0)
        result = eng.analyze_distribution()
        assert FootprintType.DOMAIN.value in result
        assert result[FootprintType.DOMAIN.value]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(risk_threshold=80.0)
        eng.record_footprint(asset_name="a", risk_score=60.0)
        eng.record_footprint(asset_name="b", risk_score=90.0)
        results = eng.identify_gaps()
        assert len(results) == 1

    def test_sorted_ascending(self):
        eng = _engine(risk_threshold=80.0)
        eng.record_footprint(asset_name="a", risk_score=50.0)
        eng.record_footprint(asset_name="b", risk_score=30.0)
        results = eng.identify_gaps()
        assert results[0]["risk_score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_gaps() == []


class TestRankByScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_footprint(asset_name="a", service="auth", risk_score=90.0)
        eng.record_footprint(asset_name="b", service="api", risk_score=50.0)
        results = eng.rank_by_score()
        assert results[0]["service"] == "api"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_score() == []


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(asset_name="t", analysis_score=50.0)
        assert eng.detect_trends()["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(asset_name="a", analysis_score=20.0)
        eng.add_analysis(asset_name="b", analysis_score=20.0)
        eng.add_analysis(asset_name="c", analysis_score=80.0)
        eng.add_analysis(asset_name="d", analysis_score=80.0)
        assert eng.detect_trends()["trend"] == "improving"

    def test_insufficient_data(self):
        eng = _engine()
        assert eng.detect_trends()["trend"] == "insufficient_data"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(risk_threshold=80.0)
        eng.record_footprint(asset_name="test", risk_score=50.0)
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
        eng.record_footprint(asset_name="test")
        eng.add_analysis(asset_name="test")
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
        eng.record_footprint(asset_name="test", service="auth", team="sec")
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
