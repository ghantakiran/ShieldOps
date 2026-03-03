"""Tests for shieldops.security.deception_telemetry_analyzer — DeceptionTelemetryAnalyzer."""

from __future__ import annotations

from shieldops.security.deception_telemetry_analyzer import (
    DeceptionTelemetryAnalysis,
    DeceptionTelemetryAnalyzer,
    DeceptionTelemetryRecord,
    DeceptionTelemetryReport,
    DeceptionType,
    InteractionRisk,
    InteractionSource,
)


def _engine(**kw) -> DeceptionTelemetryAnalyzer:
    return DeceptionTelemetryAnalyzer(**kw)


class TestEnums:
    def test_deception_type_honeypot(self):
        assert DeceptionType.HONEYPOT == "honeypot"

    def test_deception_type_honeytoken(self):
        assert DeceptionType.HONEYTOKEN == "honeytoken"

    def test_deception_type_breadcrumb(self):
        assert DeceptionType.BREADCRUMB == "breadcrumb"

    def test_deception_type_decoy_service(self):
        assert DeceptionType.DECOY_SERVICE == "decoy_service"

    def test_deception_type_trap_account(self):
        assert DeceptionType.TRAP_ACCOUNT == "trap_account"

    def test_interaction_source_network_probe(self):
        assert InteractionSource.NETWORK_PROBE == "network_probe"

    def test_interaction_source_auth_attempt(self):
        assert InteractionSource.AUTH_ATTEMPT == "auth_attempt"

    def test_interaction_source_file_access(self):
        assert InteractionSource.FILE_ACCESS == "file_access"

    def test_interaction_source_api_call(self):
        assert InteractionSource.API_CALL == "api_call"

    def test_interaction_source_lateral(self):
        assert InteractionSource.LATERAL == "lateral"

    def test_interaction_risk_critical(self):
        assert InteractionRisk.CRITICAL == "critical"

    def test_interaction_risk_high(self):
        assert InteractionRisk.HIGH == "high"

    def test_interaction_risk_medium(self):
        assert InteractionRisk.MEDIUM == "medium"

    def test_interaction_risk_low(self):
        assert InteractionRisk.LOW == "low"

    def test_interaction_risk_recon(self):
        assert InteractionRisk.RECON == "recon"


class TestModels:
    def test_record_defaults(self):
        r = DeceptionTelemetryRecord()
        assert r.id
        assert r.name == ""
        assert r.deception_type == DeceptionType.HONEYPOT
        assert r.interaction_source == InteractionSource.NETWORK_PROBE
        assert r.interaction_risk == InteractionRisk.RECON
        assert r.score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_analysis_defaults(self):
        a = DeceptionTelemetryAnalysis()
        assert a.id
        assert a.name == ""
        assert a.deception_type == DeceptionType.HONEYPOT
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = DeceptionTelemetryReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_score == 0.0
        assert r.by_deception_type == {}
        assert r.by_interaction_source == {}
        assert r.by_interaction_risk == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_entry(
            name="test-001",
            deception_type=DeceptionType.HONEYPOT,
            interaction_source=InteractionSource.AUTH_ATTEMPT,
            interaction_risk=InteractionRisk.CRITICAL,
            score=85.0,
            service="svc-a",
            team="team-a",
        )
        assert r.name == "test-001"
        assert r.deception_type == DeceptionType.HONEYPOT
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

    def test_filter_by_deception_type(self):
        eng = _engine()
        eng.record_entry(name="a", deception_type=DeceptionType.HONEYPOT)
        eng.record_entry(name="b", deception_type=DeceptionType.HONEYTOKEN)
        assert len(eng.list_records(deception_type=DeceptionType.HONEYPOT)) == 1

    def test_filter_by_interaction_source(self):
        eng = _engine()
        eng.record_entry(name="a", interaction_source=InteractionSource.NETWORK_PROBE)
        eng.record_entry(name="b", interaction_source=InteractionSource.AUTH_ATTEMPT)
        assert len(eng.list_records(interaction_source=InteractionSource.NETWORK_PROBE)) == 1

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
        eng.record_entry(name="a", deception_type=DeceptionType.HONEYTOKEN, score=90.0)
        eng.record_entry(name="b", deception_type=DeceptionType.HONEYTOKEN, score=70.0)
        result = eng.analyze_distribution()
        assert "honeytoken" in result
        assert result["honeytoken"]["count"] == 2

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
