"""Tests for shieldops.security.threat_intel_fusion_engine — ThreatIntelFusionEngine."""

from __future__ import annotations

from shieldops.security.threat_intel_fusion_engine import (
    ThreatIntelAnalysis,
    ThreatIntelFusionEngine,
    ThreatIntelLevel,
    ThreatIntelRecord,
    ThreatIntelReport,
    ThreatIntelSource,
    ThreatIntelType,
)


def _engine(**kw) -> ThreatIntelFusionEngine:
    return ThreatIntelFusionEngine(**kw)


class TestEnums:
    def test_type_vulnerability(self):
        assert ThreatIntelType.VULNERABILITY == "vulnerability"

    def test_type_misconfiguration(self):
        assert ThreatIntelType.MISCONFIGURATION == "misconfiguration"

    def test_type_threat(self):
        assert ThreatIntelType.THREAT == "threat"

    def test_type_policy_violation(self):
        assert ThreatIntelType.POLICY_VIOLATION == "policy_violation"

    def test_type_anomaly(self):
        assert ThreatIntelType.ANOMALY == "anomaly"

    def test_source_scanner(self):
        assert ThreatIntelSource.SCANNER == "scanner"

    def test_source_siem(self):
        assert ThreatIntelSource.SIEM == "siem"

    def test_source_edr(self):
        assert ThreatIntelSource.EDR == "edr"

    def test_source_cloud_audit(self):
        assert ThreatIntelSource.CLOUD_AUDIT == "cloud_audit"

    def test_source_manual(self):
        assert ThreatIntelSource.MANUAL == "manual"

    def test_level_critical(self):
        assert ThreatIntelLevel.CRITICAL == "critical"

    def test_level_high(self):
        assert ThreatIntelLevel.HIGH == "high"

    def test_level_medium(self):
        assert ThreatIntelLevel.MEDIUM == "medium"

    def test_level_low(self):
        assert ThreatIntelLevel.LOW == "low"

    def test_level_info(self):
        assert ThreatIntelLevel.INFO == "info"


class TestModels:
    def test_record_defaults(self):
        r = ThreatIntelRecord()
        assert r.id
        assert r.name == ""
        assert r.record_type == ThreatIntelType.VULNERABILITY
        assert r.source == ThreatIntelSource.SCANNER
        assert r.level == ThreatIntelLevel.MEDIUM
        assert r.score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_analysis_defaults(self):
        a = ThreatIntelAnalysis()
        assert a.id
        assert a.name == ""
        assert a.analysis_type == ThreatIntelType.VULNERABILITY
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = ThreatIntelReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_score == 0.0
        assert r.by_type == {}
        assert r.by_source == {}
        assert r.by_level == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0

    def test_record_custom(self):
        r = ThreatIntelRecord(
            name="test",
            score=75.0,
            service="api",
            team="sre",
        )
        assert r.name == "test"
        assert r.score == 75.0
        assert r.service == "api"
        assert r.team == "sre"

    def test_analysis_custom(self):
        a = ThreatIntelAnalysis(
            name="test",
            analysis_score=80.0,
            breached=True,
        )
        assert a.name == "test"
        assert a.analysis_score == 80.0
        assert a.breached is True


class TestRecord:
    def test_record_basic(self):
        e = _engine()
        rec = e.record("item-1")
        assert rec.id
        assert rec.name == "item-1"

    def test_record_with_params(self):
        e = _engine()
        rec = e.record("item-2", score=80.0, service="api", team="sre")
        assert rec.name == "item-2"
        assert rec.score == 80.0
        assert rec.service == "api"
        assert rec.team == "sre"

    def test_record_max_records(self):
        e = _engine(max_records=3)
        for i in range(5):
            e.record(f"item-{i}")
        assert len(e._records) == 3

    def test_get_record(self):
        e = _engine()
        rec = e.record("item-1")
        found = e.get_record(rec.id)
        assert found is not None
        assert found.id == rec.id

    def test_get_record_not_found(self):
        e = _engine()
        assert e.get_record("nonexistent") is None

    def test_list_records_empty(self):
        e = _engine()
        assert e.list_records() == []

    def test_list_records_with_data(self):
        e = _engine()
        e.record("a")
        e.record("b")
        assert len(e.list_records()) == 2

    def test_list_records_filter_type(self):
        e = _engine()
        e.record("a", record_type=ThreatIntelType.VULNERABILITY)
        e.record("b", record_type=ThreatIntelType.MISCONFIGURATION)
        results = e.list_records(record_type=ThreatIntelType.VULNERABILITY)
        assert len(results) == 1

    def test_list_records_filter_source(self):
        e = _engine()
        e.record("a", source=ThreatIntelSource.SCANNER)
        e.record("b", source=ThreatIntelSource.SIEM)
        results = e.list_records(source=ThreatIntelSource.SCANNER)
        assert len(results) == 1

    def test_list_records_filter_team(self):
        e = _engine()
        e.record("a", team="alpha")
        e.record("b", team="beta")
        results = e.list_records(team="alpha")
        assert len(results) == 1

    def test_list_records_limit(self):
        e = _engine()
        for i in range(10):
            e.record(f"item-{i}")
        assert len(e.list_records(limit=3)) == 3


class TestAnalysis:
    def test_add_analysis(self):
        e = _engine()
        a = e.add_analysis("test-1", analysis_score=75.0)
        assert a.id
        assert a.name == "test-1"
        assert a.analysis_score == 75.0

    def test_add_analysis_with_breach(self):
        e = _engine()
        a = e.add_analysis("test-2", breached=True, description="critical")
        assert a.breached is True
        assert a.description == "critical"

    def test_analysis_max_records(self):
        e = _engine(max_records=2)
        for i in range(5):
            e.add_analysis(f"a-{i}")
        assert len(e._analyses) == 2


class TestDistribution:
    def test_empty(self):
        e = _engine()
        assert e.analyze_distribution() == {}

    def test_single_type(self):
        e = _engine()
        e.record("a", score=80.0)
        e.record("b", score=60.0)
        dist = e.analyze_distribution()
        assert dist["vulnerability"]["count"] == 2
        assert dist["vulnerability"]["avg_score"] == 70.0

    def test_multiple_types(self):
        e = _engine()
        t1 = ThreatIntelType.VULNERABILITY
        t2 = ThreatIntelType.MISCONFIGURATION
        e.record("a", record_type=t1, score=80.0)
        e.record("b", record_type=t2, score=60.0)
        dist = e.analyze_distribution()
        assert len(dist) == 2


class TestGaps:
    def test_no_gaps(self):
        e = _engine(threshold=30.0)
        e.record("a", score=80.0)
        assert e.identify_gaps() == []

    def test_with_gaps(self):
        e = _engine(threshold=50.0)
        e.record("a", score=30.0)
        e.record("b", score=80.0)
        gaps = e.identify_gaps()
        assert len(gaps) == 1
        assert gaps[0]["name"] == "a"

    def test_gaps_sorted(self):
        e = _engine(threshold=50.0)
        e.record("b", score=40.0)
        e.record("a", score=20.0)
        gaps = e.identify_gaps()
        assert gaps[0]["score"] < gaps[1]["score"]


class TestRanking:
    def test_empty(self):
        e = _engine()
        assert e.rank_by_score() == []

    def test_single_service(self):
        e = _engine()
        e.record("a", score=80.0, service="api")
        e.record("b", score=60.0, service="api")
        ranked = e.rank_by_score()
        assert len(ranked) == 1
        assert ranked[0]["avg_score"] == 70.0

    def test_multiple_services(self):
        e = _engine()
        e.record("a", score=80.0, service="api")
        e.record("b", score=40.0, service="web")
        ranked = e.rank_by_score()
        assert ranked[0]["service"] == "web"


class TestTrends:
    def test_insufficient_data(self):
        e = _engine()
        result = e.detect_trends()
        assert result["trend"] == "insufficient_data"

    def test_stable(self):
        e = _engine()
        e.add_analysis("a", analysis_score=50.0)
        e.add_analysis("b", analysis_score=52.0)
        result = e.detect_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        e = _engine()
        e.add_analysis("a", analysis_score=30.0)
        e.add_analysis("b", analysis_score=80.0)
        result = e.detect_trends()
        assert result["trend"] == "improving"

    def test_degrading(self):
        e = _engine()
        e.add_analysis("a", analysis_score=80.0)
        e.add_analysis("b", analysis_score=20.0)
        result = e.detect_trends()
        assert result["trend"] == "degrading"


class TestReport:
    def test_empty_report(self):
        e = _engine()
        report = e.generate_report()
        assert report.total_records == 0
        assert report.total_analyses == 0
        assert report.gap_count == 0
        assert report.avg_score == 0.0
        assert any("healthy" in r for r in report.recommendations)

    def test_report_with_data(self):
        e = _engine(threshold=50.0)
        e.record("a", score=30.0)
        e.record("b", score=80.0)
        report = e.generate_report()
        assert report.total_records == 2
        assert report.gap_count == 1
        assert report.avg_score == 55.0

    def test_report_recommendations_gap(self):
        e = _engine(threshold=90.0)
        e.record("a", score=30.0)
        report = e.generate_report()
        assert len(report.recommendations) >= 1
        assert any("threshold" in r for r in report.recommendations)

    def test_report_top_gaps(self):
        e = _engine(threshold=50.0)
        e.record("low-item", score=10.0)
        e.record("high-item", score=90.0)
        report = e.generate_report()
        assert "low-item" in report.top_gaps


class TestStats:
    def test_empty_stats(self):
        e = _engine()
        stats = e.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_analyses"] == 0

    def test_stats_with_data(self):
        e = _engine()
        e.record("a")
        e.add_analysis("b")
        stats = e.get_stats()
        assert stats["total_records"] == 1
        assert stats["total_analyses"] == 1

    def test_clear_data(self):
        e = _engine()
        e.record("a")
        e.add_analysis("b")
        result = e.clear_data()
        assert result["status"] == "cleared"
        assert len(e._records) == 0
        assert len(e._analyses) == 0

    def test_stats_unique_teams(self):
        e = _engine()
        e.record("a", team="alpha")
        e.record("b", team="alpha")
        e.record("c", team="beta")
        stats = e.get_stats()
        assert stats["unique_teams"] == 2

    def test_stats_unique_services(self):
        e = _engine()
        e.record("a", service="api")
        e.record("b", service="web")
        stats = e.get_stats()
        assert stats["unique_services"] == 2
