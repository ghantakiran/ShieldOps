"""Tests for shieldops.analytics.device_trust_scorer — DeviceTrustScorer."""

from __future__ import annotations

from shieldops.analytics.device_trust_scorer import (
    ComplianceStatus,
    DeviceTrustAnalysis,
    DeviceTrustRecord,
    DeviceTrustReport,
    DeviceTrustScorer,
    DeviceType,
    TrustLevel,
)


def _engine(**kw) -> DeviceTrustScorer:
    return DeviceTrustScorer(**kw)


class TestEnums:
    def test_device_managed(self):
        assert DeviceType.MANAGED == "managed"

    def test_device_unmanaged(self):
        assert DeviceType.UNMANAGED == "unmanaged"

    def test_device_byod(self):
        assert DeviceType.BYOD == "byod"

    def test_device_iot(self):
        assert DeviceType.IOT == "iot"

    def test_device_virtual(self):
        assert DeviceType.VIRTUAL == "virtual"

    def test_compliance_compliant(self):
        assert ComplianceStatus.COMPLIANT == "compliant"

    def test_compliance_non_compliant(self):
        assert ComplianceStatus.NON_COMPLIANT == "non_compliant"

    def test_compliance_partial(self):
        assert ComplianceStatus.PARTIAL == "partial"

    def test_compliance_unknown(self):
        assert ComplianceStatus.UNKNOWN == "unknown"

    def test_compliance_exempt(self):
        assert ComplianceStatus.EXEMPT == "exempt"

    def test_trust_high(self):
        assert TrustLevel.HIGH == "high"

    def test_trust_medium(self):
        assert TrustLevel.MEDIUM == "medium"

    def test_trust_low(self):
        assert TrustLevel.LOW == "low"

    def test_trust_untrusted(self):
        assert TrustLevel.UNTRUSTED == "untrusted"

    def test_trust_blocked(self):
        assert TrustLevel.BLOCKED == "blocked"


class TestModels:
    def test_record_defaults(self):
        r = DeviceTrustRecord()
        assert r.id
        assert r.device_name == ""
        assert r.device_type == DeviceType.MANAGED
        assert r.compliance_status == ComplianceStatus.COMPLIANT
        assert r.trust_level == TrustLevel.HIGH
        assert r.trust_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_analysis_defaults(self):
        a = DeviceTrustAnalysis()
        assert a.id
        assert a.device_name == ""
        assert a.device_type == DeviceType.MANAGED
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = DeviceTrustReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_trust_score == 0.0
        assert r.by_device_type == {}
        assert r.by_compliance_status == {}
        assert r.by_trust_level == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_trust(
            device_name="laptop-001",
            device_type=DeviceType.UNMANAGED,
            compliance_status=ComplianceStatus.NON_COMPLIANT,
            trust_level=TrustLevel.LOW,
            trust_score=85.0,
            service="mdm-svc",
            team="it-ops",
        )
        assert r.device_name == "laptop-001"
        assert r.device_type == DeviceType.UNMANAGED
        assert r.trust_score == 85.0
        assert r.service == "mdm-svc"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_trust(device_name=f"dev-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_trust(device_name="test")
        assert eng.get_record(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_record("nonexistent") is None


class TestList:
    def test_list_all(self):
        eng = _engine()
        eng.record_trust(device_name="a")
        eng.record_trust(device_name="b")
        assert len(eng.list_records()) == 2

    def test_filter_by_device_type(self):
        eng = _engine()
        eng.record_trust(device_name="a", device_type=DeviceType.MANAGED)
        eng.record_trust(device_name="b", device_type=DeviceType.UNMANAGED)
        assert len(eng.list_records(device_type=DeviceType.MANAGED)) == 1

    def test_filter_by_compliance_status(self):
        eng = _engine()
        eng.record_trust(device_name="a", compliance_status=ComplianceStatus.COMPLIANT)
        eng.record_trust(device_name="b", compliance_status=ComplianceStatus.NON_COMPLIANT)
        assert len(eng.list_records(compliance_status=ComplianceStatus.COMPLIANT)) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_trust(device_name="a", team="sec")
        eng.record_trust(device_name="b", team="ops")
        assert len(eng.list_records(team="sec")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_trust(device_name=f"d-{i}")
        assert len(eng.list_records(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            device_name="test", analysis_score=88.5, breached=True, description="non-compliant"
        )
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(device_name=f"t-{i}")
        assert len(eng._analyses) == 2


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_trust(device_name="a", device_type=DeviceType.MANAGED, trust_score=90.0)
        eng.record_trust(device_name="b", device_type=DeviceType.MANAGED, trust_score=70.0)
        result = eng.analyze_distribution()
        assert "managed" in result
        assert result["managed"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(threshold=80.0)
        eng.record_trust(device_name="a", trust_score=60.0)
        eng.record_trust(device_name="b", trust_score=90.0)
        assert len(eng.identify_gaps()) == 1

    def test_sorted_ascending(self):
        eng = _engine(threshold=80.0)
        eng.record_trust(device_name="a", trust_score=50.0)
        eng.record_trust(device_name="b", trust_score=30.0)
        results = eng.identify_gaps()
        assert results[0]["trust_score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_gaps() == []


class TestRankByScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_trust(device_name="a", service="auth", trust_score=90.0)
        eng.record_trust(device_name="b", service="api", trust_score=50.0)
        results = eng.rank_by_score()
        assert results[0]["service"] == "api"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_score() == []


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(device_name="t", analysis_score=50.0)
        assert eng.detect_trends()["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(device_name="a", analysis_score=20.0)
        eng.add_analysis(device_name="b", analysis_score=20.0)
        eng.add_analysis(device_name="c", analysis_score=80.0)
        eng.add_analysis(device_name="d", analysis_score=80.0)
        assert eng.detect_trends()["trend"] == "improving"

    def test_insufficient_data(self):
        eng = _engine()
        assert eng.detect_trends()["trend"] == "insufficient_data"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(threshold=80.0)
        eng.record_trust(device_name="test", trust_score=50.0)
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
        eng.record_trust(device_name="test")
        eng.add_analysis(device_name="test")
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
        eng.record_trust(device_name="test", service="auth", team="sec")
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
