"""Tests for certificate_transparency_monitor — CertificateTransparencyMonitor."""

from __future__ import annotations

from shieldops.security.certificate_transparency_monitor import (
    CertificateTransparencyMonitor,
    CertStatus,
    CertTransparencyAnalysis,
    CertTransparencyRecord,
    CertTransparencyReport,
    CertType,
    MonitoringAction,
)


def _engine(**kw) -> CertificateTransparencyMonitor:
    return CertificateTransparencyMonitor(**kw)


class TestEnums:
    def test_certtype_val1(self):
        assert CertType.DV == "dv"

    def test_certtype_val2(self):
        assert CertType.OV == "ov"

    def test_certtype_val3(self):
        assert CertType.EV == "ev"

    def test_certtype_val4(self):
        assert CertType.SELF_SIGNED == "self_signed"

    def test_certtype_val5(self):
        assert CertType.WILDCARD == "wildcard"

    def test_certstatus_val1(self):
        assert CertStatus.VALID == "valid"

    def test_certstatus_val2(self):
        assert CertStatus.EXPIRING == "expiring"

    def test_certstatus_val3(self):
        assert CertStatus.EXPIRED == "expired"

    def test_certstatus_val4(self):
        assert CertStatus.REVOKED == "revoked"

    def test_certstatus_val5(self):
        assert CertStatus.UNKNOWN == "unknown"

    def test_monitoringaction_val1(self):
        assert MonitoringAction.ALERT == "alert"

    def test_monitoringaction_val2(self):
        assert MonitoringAction.INVESTIGATE == "investigate"

    def test_monitoringaction_val3(self):
        assert MonitoringAction.BLOCK == "block"

    def test_monitoringaction_val4(self):
        assert MonitoringAction.RENEW == "renew"

    def test_monitoringaction_val5(self):
        assert MonitoringAction.IGNORE == "ignore"


class TestModels:
    def test_record_defaults(self):
        r = CertTransparencyRecord()
        assert r.id
        assert r.domain_name == ""

    def test_analysis_defaults(self):
        a = CertTransparencyAnalysis()
        assert a.id
        assert a.analysis_score == 0.0
        assert a.breached is False

    def test_report_defaults(self):
        r = CertTransparencyReport()
        assert r.total_records == 0
        assert r.recommendations == []


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_certificate(
            domain_name="test", cert_type=CertType.OV, risk_score=92.0, service="auth", team="sec"
        )
        assert r.domain_name == "test"
        assert r.risk_score == 92.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_certificate(domain_name=f"t-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_certificate(domain_name="test")
        assert eng.get_certificate(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_certificate("nope") is None


class TestList:
    def test_list_all(self):
        eng = _engine()
        eng.record_certificate(domain_name="a")
        eng.record_certificate(domain_name="b")
        assert len(eng.list_certificates()) == 2

    def test_filter_by_enum1(self):
        eng = _engine()
        eng.record_certificate(domain_name="a", cert_type=CertType.DV)
        eng.record_certificate(domain_name="b", cert_type=CertType.OV)
        assert len(eng.list_certificates(cert_type=CertType.DV)) == 1

    def test_filter_by_enum2(self):
        eng = _engine()
        eng.record_certificate(domain_name="a", cert_status=CertStatus.VALID)
        eng.record_certificate(domain_name="b", cert_status=CertStatus.EXPIRING)
        assert len(eng.list_certificates(cert_status=CertStatus.VALID)) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_certificate(domain_name="a", team="sec")
        eng.record_certificate(domain_name="b", team="ops")
        assert len(eng.list_certificates(team="sec")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_certificate(domain_name=f"t-{i}")
        assert len(eng.list_certificates(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            domain_name="test", analysis_score=88.5, breached=True, description="gap"
        )
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(domain_name=f"t-{i}")
        assert len(eng._analyses) == 2


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_certificate(domain_name="a", cert_type=CertType.DV, risk_score=90.0)
        eng.record_certificate(domain_name="b", cert_type=CertType.DV, risk_score=70.0)
        result = eng.analyze_distribution()
        assert CertType.DV.value in result
        assert result[CertType.DV.value]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(risk_threshold=80.0)
        eng.record_certificate(domain_name="a", risk_score=60.0)
        eng.record_certificate(domain_name="b", risk_score=90.0)
        results = eng.identify_gaps()
        assert len(results) == 1

    def test_sorted_ascending(self):
        eng = _engine(risk_threshold=80.0)
        eng.record_certificate(domain_name="a", risk_score=50.0)
        eng.record_certificate(domain_name="b", risk_score=30.0)
        results = eng.identify_gaps()
        assert results[0]["risk_score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_gaps() == []


class TestRankByScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_certificate(domain_name="a", service="auth", risk_score=90.0)
        eng.record_certificate(domain_name="b", service="api", risk_score=50.0)
        results = eng.rank_by_score()
        assert results[0]["service"] == "api"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_score() == []


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(domain_name="t", analysis_score=50.0)
        assert eng.detect_trends()["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(domain_name="a", analysis_score=20.0)
        eng.add_analysis(domain_name="b", analysis_score=20.0)
        eng.add_analysis(domain_name="c", analysis_score=80.0)
        eng.add_analysis(domain_name="d", analysis_score=80.0)
        assert eng.detect_trends()["trend"] == "improving"

    def test_insufficient_data(self):
        eng = _engine()
        assert eng.detect_trends()["trend"] == "insufficient_data"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(risk_threshold=80.0)
        eng.record_certificate(domain_name="test", risk_score=50.0)
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
        eng.record_certificate(domain_name="test")
        eng.add_analysis(domain_name="test")
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
        eng.record_certificate(domain_name="test", service="auth", team="sec")
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
