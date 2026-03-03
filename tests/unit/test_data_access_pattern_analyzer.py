"""Tests for shieldops.security.data_access_pattern_analyzer — DataAccessPatternAnalyzer."""

from __future__ import annotations

from shieldops.security.data_access_pattern_analyzer import (
    AccessPattern,
    AccessPatternAnalysis,
    AccessPatternRecord,
    AccessPatternReport,
    DataAccessPatternAnalyzer,
    PatternRisk,
    PatternSource,
)


def _engine(**kw) -> DataAccessPatternAnalyzer:
    return DataAccessPatternAnalyzer(**kw)


class TestEnums:
    def test_e1_v1(self):
        assert AccessPattern.NORMAL == "normal"

    def test_e1_v2(self):
        assert AccessPattern.BULK_READ == "bulk_read"

    def test_e1_v3(self):
        assert AccessPattern.OFF_HOURS == "off_hours"

    def test_e1_v4(self):
        assert AccessPattern.NEW_RESOURCE == "new_resource"

    def test_e1_v5(self):
        assert AccessPattern.PRIVILEGE_ESCALATION == "privilege_escalation"

    def test_e2_v1(self):
        assert PatternSource.AUDIT_LOG == "audit_log"

    def test_e2_v2(self):
        assert PatternSource.DLP == "dlp"

    def test_e2_v3(self):
        assert PatternSource.DATABASE_MONITOR == "database_monitor"

    def test_e2_v4(self):
        assert PatternSource.API_GATEWAY == "api_gateway"

    def test_e2_v5(self):
        assert PatternSource.IDENTITY_PROVIDER == "identity_provider"

    def test_e3_v1(self):
        assert PatternRisk.CRITICAL == "critical"

    def test_e3_v2(self):
        assert PatternRisk.HIGH == "high"

    def test_e3_v3(self):
        assert PatternRisk.MEDIUM == "medium"

    def test_e3_v4(self):
        assert PatternRisk.LOW == "low"

    def test_e3_v5(self):
        assert PatternRisk.BASELINE == "baseline"


class TestModels:
    def test_rec(self):
        r = AccessPatternRecord()
        assert r.id and r.pattern_score == 0.0 and r.service == ""

    def test_analysis(self):
        a = AccessPatternAnalysis()
        assert a.id and a.analysis_score == 0.0 and a.breached is False

    def test_report(self):
        r = AccessPatternReport()
        assert r.id and r.total_records == 0


class TestRecord:
    def test_basic(self):
        r = _engine().record_pattern(
            pattern_id="t",
            access_pattern=AccessPattern.BULK_READ,
            pattern_source=PatternSource.DLP,
            pattern_risk=PatternRisk.HIGH,
            pattern_score=92.0,
            service="s",
            team="t",
        )
        assert r.pattern_id == "t" and r.pattern_score == 92.0

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_pattern(pattern_id=f"t-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_pattern(pattern_id="t")
        assert eng.get_pattern(r.id) is not None

    def test_not_found(self):
        assert _engine().get_pattern("x") is None


class TestList:
    def test_all(self):
        eng = _engine()
        eng.record_pattern(pattern_id="a")
        eng.record_pattern(pattern_id="b")
        assert len(eng.list_patterns()) == 2

    def test_e1(self):
        eng = _engine()
        eng.record_pattern(pattern_id="a", access_pattern=AccessPattern.NORMAL)
        eng.record_pattern(pattern_id="b", access_pattern=AccessPattern.BULK_READ)
        assert len(eng.list_patterns(access_pattern=AccessPattern.NORMAL)) == 1

    def test_e2(self):
        eng = _engine()
        eng.record_pattern(pattern_id="a", pattern_source=PatternSource.AUDIT_LOG)
        eng.record_pattern(pattern_id="b", pattern_source=PatternSource.DLP)
        assert len(eng.list_patterns(pattern_source=PatternSource.AUDIT_LOG)) == 1

    def test_team(self):
        eng = _engine()
        eng.record_pattern(pattern_id="a", team="x")
        eng.record_pattern(pattern_id="b", team="y")
        assert len(eng.list_patterns(team="x")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_pattern(pattern_id=f"t-{i}")
        assert len(eng.list_patterns(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        a = _engine().add_analysis(
            pattern_id="t",
            access_pattern=AccessPattern.BULK_READ,
            analysis_score=88.5,
            breached=True,
        )
        assert a.analysis_score == 88.5 and a.breached is True

    def test_eviction(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(pattern_id=f"t-{i}")
        assert len(eng._analyses) == 2


class TestDistribution:
    def test_data(self):
        eng = _engine()
        eng.record_pattern(pattern_id="a", access_pattern=AccessPattern.NORMAL, pattern_score=90.0)
        eng.record_pattern(pattern_id="b", access_pattern=AccessPattern.NORMAL, pattern_score=70.0)
        assert "normal" in eng.analyze_pattern_distribution()

    def test_empty(self):
        assert _engine().analyze_pattern_distribution() == {}


class TestGaps:
    def test_below(self):
        eng = _engine(pattern_threshold=80.0)
        eng.record_pattern(pattern_id="a", pattern_score=60.0)
        eng.record_pattern(pattern_id="b", pattern_score=90.0)
        assert len(eng.identify_pattern_gaps()) == 1

    def test_sorted(self):
        eng = _engine(pattern_threshold=80.0)
        eng.record_pattern(pattern_id="a", pattern_score=50.0)
        eng.record_pattern(pattern_id="b", pattern_score=30.0)
        assert len(eng.identify_pattern_gaps()) == 2


class TestRank:
    def test_data(self):
        eng = _engine()
        eng.record_pattern(pattern_id="a", service="s1", pattern_score=80.0)
        eng.record_pattern(pattern_id="b", service="s2", pattern_score=60.0)
        assert eng.rank_by_pattern()[0]["service"] == "s2"

    def test_empty(self):
        assert _engine().rank_by_pattern() == []


class TestTrends:
    def test_improving(self):
        eng = _engine()
        for v in [10, 20, 30, 40, 50, 60, 70, 80]:
            eng.add_analysis(pattern_id="t", analysis_score=float(v))
        assert eng.detect_pattern_trends()["trend"] == "improving"

    def test_stable(self):
        eng = _engine()
        for v in [50, 51, 49, 50]:
            eng.add_analysis(pattern_id="t", analysis_score=float(v))
        assert eng.detect_pattern_trends()["trend"] == "stable"

    def test_insufficient(self):
        assert _engine().detect_pattern_trends()["trend"] == "insufficient_data"


class TestReport:
    def test_data(self):
        eng = _engine()
        eng.record_pattern(pattern_id="t", pattern_score=90.0)
        assert eng.generate_report().total_records == 1

    def test_empty(self):
        assert _engine().generate_report().total_records == 0


class TestClear:
    def test_clears(self):
        eng = _engine()
        eng.record_pattern(pattern_id="t")
        eng.add_analysis(pattern_id="t")
        eng.clear_data()
        assert len(eng._records) == 0 and len(eng._analyses) == 0


class TestStats:
    def test_data(self):
        eng = _engine()
        eng.record_pattern(pattern_id="t", team="s", service="v")
        assert eng.get_stats()["total_records"] == 1

    def test_empty(self):
        assert _engine().get_stats()["total_records"] == 0

    def test_counts(self):
        eng = _engine()
        eng.record_pattern(pattern_id="a")
        eng.record_pattern(pattern_id="b")
        eng.add_analysis(pattern_id="t")
        assert eng.get_stats()["total_records"] == 2 and eng.get_stats()["total_analyses"] == 1
