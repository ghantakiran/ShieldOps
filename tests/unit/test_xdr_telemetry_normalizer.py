"""Tests for shieldops.security.xdr_telemetry_normalizer — XdrTelemetryNormalizer."""

from __future__ import annotations

from shieldops.security.xdr_telemetry_normalizer import (
    NormalizationAnalysis,
    NormalizationQuality,
    NormalizationRecord,
    TelemetryDomain,
    TelemetryFormat,
    XdrTelemetryNormalizer,
    XdrTelemetryReport,
)


def _engine(**kw) -> XdrTelemetryNormalizer:
    return XdrTelemetryNormalizer(**kw)


class TestEnums:
    def test_telemetry_format_ecs(self):
        assert TelemetryFormat.ECS == "ecs"

    def test_telemetry_format_ocsf(self):
        assert TelemetryFormat.OCSF == "ocsf"

    def test_telemetry_format_cef(self):
        assert TelemetryFormat.CEF == "cef"

    def test_telemetry_format_leef(self):
        assert TelemetryFormat.LEEF == "leef"

    def test_telemetry_format_custom(self):
        assert TelemetryFormat.CUSTOM == "custom"

    def test_telemetry_domain_endpoint(self):
        assert TelemetryDomain.ENDPOINT == "endpoint"

    def test_telemetry_domain_network(self):
        assert TelemetryDomain.NETWORK == "network"

    def test_telemetry_domain_cloud(self):
        assert TelemetryDomain.CLOUD == "cloud"

    def test_telemetry_domain_identity(self):
        assert TelemetryDomain.IDENTITY == "identity"

    def test_telemetry_domain_email(self):
        assert TelemetryDomain.EMAIL == "email"

    def test_normalization_quality_complete(self):
        assert NormalizationQuality.COMPLETE == "complete"

    def test_normalization_quality_partial(self):
        assert NormalizationQuality.PARTIAL == "partial"

    def test_normalization_quality_lossy(self):
        assert NormalizationQuality.LOSSY == "lossy"

    def test_normalization_quality_failed(self):
        assert NormalizationQuality.FAILED == "failed"

    def test_normalization_quality_unknown(self):
        assert NormalizationQuality.UNKNOWN == "unknown"


class TestModels:
    def test_record_defaults(self):
        r = NormalizationRecord()
        assert r.id
        assert r.name == ""
        assert r.telemetry_format == TelemetryFormat.ECS
        assert r.telemetry_domain == TelemetryDomain.ENDPOINT
        assert r.normalization_quality == NormalizationQuality.UNKNOWN
        assert r.score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_analysis_defaults(self):
        a = NormalizationAnalysis()
        assert a.id
        assert a.name == ""
        assert a.telemetry_format == TelemetryFormat.ECS
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = XdrTelemetryReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_score == 0.0
        assert r.by_telemetry_format == {}
        assert r.by_telemetry_domain == {}
        assert r.by_normalization_quality == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_entry(
            name="test-001",
            telemetry_format=TelemetryFormat.ECS,
            telemetry_domain=TelemetryDomain.NETWORK,
            normalization_quality=NormalizationQuality.COMPLETE,
            score=85.0,
            service="svc-a",
            team="team-a",
        )
        assert r.name == "test-001"
        assert r.telemetry_format == TelemetryFormat.ECS
        assert r.score == 85.0
        assert r.service == "svc-a"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_entry(name=f"item-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_entry(name="test")
        assert eng.get_record(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_record("nonexistent") is None


class TestList:
    def test_list_all(self):
        eng = _engine()
        eng.record_entry(name="a")
        eng.record_entry(name="b")
        assert len(eng.list_records()) == 2

    def test_filter_by_telemetry_format(self):
        eng = _engine()
        eng.record_entry(name="a", telemetry_format=TelemetryFormat.ECS)
        eng.record_entry(name="b", telemetry_format=TelemetryFormat.OCSF)
        assert len(eng.list_records(telemetry_format=TelemetryFormat.ECS)) == 1

    def test_filter_by_telemetry_domain(self):
        eng = _engine()
        eng.record_entry(name="a", telemetry_domain=TelemetryDomain.ENDPOINT)
        eng.record_entry(name="b", telemetry_domain=TelemetryDomain.NETWORK)
        assert len(eng.list_records(telemetry_domain=TelemetryDomain.ENDPOINT)) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_entry(name="a", team="sec")
        eng.record_entry(name="b", team="ops")
        assert len(eng.list_records(team="sec")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_entry(name=f"a-{i}")
        assert len(eng.list_records(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            name="test",
            analysis_score=88.5,
            breached=True,
            description="confirmed issue",
        )
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(name=f"t-{i}")
        assert len(eng._analyses) == 2


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_entry(name="a", telemetry_format=TelemetryFormat.OCSF, score=90.0)
        eng.record_entry(name="b", telemetry_format=TelemetryFormat.OCSF, score=70.0)
        result = eng.analyze_distribution()
        assert "ocsf" in result
        assert result["ocsf"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(threshold=80.0)
        eng.record_entry(name="a", score=60.0)
        eng.record_entry(name="b", score=90.0)
        assert len(eng.identify_gaps()) == 1

    def test_sorted_ascending(self):
        eng = _engine(threshold=80.0)
        eng.record_entry(name="a", score=50.0)
        eng.record_entry(name="b", score=30.0)
        results = eng.identify_gaps()
        assert results[0]["score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_gaps() == []


class TestRankByScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_entry(name="a", service="auth", score=90.0)
        eng.record_entry(name="b", service="api", score=50.0)
        results = eng.rank_by_score()
        assert results[0]["service"] == "api"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_score() == []


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(name="t", analysis_score=50.0)
        assert eng.detect_trends()["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(name="a", analysis_score=20.0)
        eng.add_analysis(name="b", analysis_score=20.0)
        eng.add_analysis(name="c", analysis_score=80.0)
        eng.add_analysis(name="d", analysis_score=80.0)
        assert eng.detect_trends()["trend"] == "improving"

    def test_insufficient_data(self):
        eng = _engine()
        assert eng.detect_trends()["trend"] == "insufficient_data"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(threshold=80.0)
        eng.record_entry(name="test", score=50.0)
        report = eng.generate_report()
        assert report.total_records == 1
        assert report.gap_count == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_entry(name="test")
        eng.add_analysis(name="test")
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
        eng.record_entry(name="test", service="auth", team="sec")
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
