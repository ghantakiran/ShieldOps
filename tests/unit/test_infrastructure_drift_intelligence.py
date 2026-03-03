"""Tests for shieldops.operations.infrastructure_drift_intelligence

InfrastructureDriftIntelligence.
"""

from __future__ import annotations

from shieldops.operations.infrastructure_drift_intelligence import (
    DriftAnalysis,
    DriftRecord,
    DriftSeverity,
    DriftSource,
    DriftType,
    InfrastructureDriftIntelligence,
    InfrastructureDriftReport,
)


def _engine(**kw) -> InfrastructureDriftIntelligence:
    return InfrastructureDriftIntelligence(**kw)


class TestEnums:
    def test_drift_type_configuration(self):
        assert DriftType.CONFIGURATION == "configuration"

    def test_drift_type_version(self):
        assert DriftType.VERSION == "version"

    def test_drift_type_permission(self):
        assert DriftType.PERMISSION == "permission"

    def test_drift_type_resource(self):
        assert DriftType.RESOURCE == "resource"

    def test_drift_type_network(self):
        assert DriftType.NETWORK == "network"

    def test_drift_source_terraform_state(self):
        assert DriftSource.TERRAFORM_STATE == "terraform_state"

    def test_drift_source_cloud_api(self):
        assert DriftSource.CLOUD_API == "cloud_api"

    def test_drift_source_agent_scan(self):
        assert DriftSource.AGENT_SCAN == "agent_scan"

    def test_drift_source_audit_log(self):
        assert DriftSource.AUDIT_LOG == "audit_log"

    def test_drift_source_manual(self):
        assert DriftSource.MANUAL == "manual"

    def test_drift_severity_critical(self):
        assert DriftSeverity.CRITICAL == "critical"

    def test_drift_severity_high(self):
        assert DriftSeverity.HIGH == "high"

    def test_drift_severity_medium(self):
        assert DriftSeverity.MEDIUM == "medium"

    def test_drift_severity_low(self):
        assert DriftSeverity.LOW == "low"

    def test_drift_severity_cosmetic(self):
        assert DriftSeverity.COSMETIC == "cosmetic"


class TestModels:
    def test_record_defaults(self):
        r = DriftRecord()
        assert r.id
        assert r.name == ""
        assert r.drift_type == DriftType.CONFIGURATION
        assert r.drift_source == DriftSource.TERRAFORM_STATE
        assert r.drift_severity == DriftSeverity.COSMETIC
        assert r.score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_analysis_defaults(self):
        a = DriftAnalysis()
        assert a.id
        assert a.name == ""
        assert a.drift_type == DriftType.CONFIGURATION
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = InfrastructureDriftReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_score == 0.0
        assert r.by_drift_type == {}
        assert r.by_drift_source == {}
        assert r.by_drift_severity == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_entry(
            name="test-001",
            drift_type=DriftType.CONFIGURATION,
            drift_source=DriftSource.CLOUD_API,
            drift_severity=DriftSeverity.CRITICAL,
            score=85.0,
            service="svc-a",
            team="team-a",
        )
        assert r.name == "test-001"
        assert r.drift_type == DriftType.CONFIGURATION
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

    def test_filter_by_drift_type(self):
        eng = _engine()
        eng.record_entry(name="a", drift_type=DriftType.CONFIGURATION)
        eng.record_entry(name="b", drift_type=DriftType.VERSION)
        assert len(eng.list_records(drift_type=DriftType.CONFIGURATION)) == 1

    def test_filter_by_drift_source(self):
        eng = _engine()
        eng.record_entry(name="a", drift_source=DriftSource.TERRAFORM_STATE)
        eng.record_entry(name="b", drift_source=DriftSource.CLOUD_API)
        assert len(eng.list_records(drift_source=DriftSource.TERRAFORM_STATE)) == 1

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
        eng.record_entry(name="a", drift_type=DriftType.VERSION, score=90.0)
        eng.record_entry(name="b", drift_type=DriftType.VERSION, score=70.0)
        result = eng.analyze_distribution()
        assert "version" in result
        assert result["version"]["count"] == 2

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
