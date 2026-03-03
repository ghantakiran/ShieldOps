"""Tests for shieldops.security.credential_abuse_detector — CredentialAbuseDetector."""

from __future__ import annotations

from shieldops.security.credential_abuse_detector import (
    AbuseAnalysis,
    AbuseConfidence,
    AbuseRecord,
    AbuseType,
    CredentialAbuseDetector,
    CredentialAbuseReport,
    DetectionSource,
)


def _engine(**kw) -> CredentialAbuseDetector:
    return CredentialAbuseDetector(**kw)


class TestEnums:
    def test_abuse_credential_stuffing(self):
        assert AbuseType.CREDENTIAL_STUFFING == "credential_stuffing"  # noqa: S105

    def test_abuse_brute_force(self):
        assert AbuseType.BRUTE_FORCE == "brute_force"

    def test_abuse_token_theft(self):
        assert AbuseType.TOKEN_THEFT == "token_theft"  # noqa: S105

    def test_abuse_session_hijack(self):
        assert AbuseType.SESSION_HIJACK == "session_hijack"

    def test_abuse_password_spray(self):
        assert AbuseType.PASSWORD_SPRAY == "password_spray"  # noqa: S105

    def test_source_authentication_log(self):
        assert DetectionSource.AUTHENTICATION_LOG == "authentication_log"

    def test_source_network_traffic(self):
        assert DetectionSource.NETWORK_TRAFFIC == "network_traffic"

    def test_source_endpoint_telemetry(self):
        assert DetectionSource.ENDPOINT_TELEMETRY == "endpoint_telemetry"

    def test_source_cloud_audit(self):
        assert DetectionSource.CLOUD_AUDIT == "cloud_audit"

    def test_source_identity_provider(self):
        assert DetectionSource.IDENTITY_PROVIDER == "identity_provider"

    def test_confidence_low(self):
        assert AbuseConfidence.LOW == "low"

    def test_confidence_medium(self):
        assert AbuseConfidence.MEDIUM == "medium"

    def test_confidence_high(self):
        assert AbuseConfidence.HIGH == "high"

    def test_confidence_confirmed(self):
        assert AbuseConfidence.CONFIRMED == "confirmed"

    def test_confidence_suspected(self):
        assert AbuseConfidence.SUSPECTED == "suspected"


class TestModels:
    def test_record_defaults(self):
        r = AbuseRecord()
        assert r.id
        assert r.credential_name == ""
        assert r.abuse_type == AbuseType.BRUTE_FORCE
        assert r.detection_source == DetectionSource.AUTHENTICATION_LOG
        assert r.abuse_confidence == AbuseConfidence.SUSPECTED
        assert r.abuse_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_analysis_defaults(self):
        a = AbuseAnalysis()
        assert a.id
        assert a.credential_name == ""
        assert a.abuse_type == AbuseType.BRUTE_FORCE
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = CredentialAbuseReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_abuse_score == 0.0
        assert r.by_abuse_type == {}
        assert r.by_detection_source == {}
        assert r.by_abuse_confidence == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_abuse(
            credential_name="cred-stuff-001",
            abuse_type=AbuseType.BRUTE_FORCE,
            detection_source=DetectionSource.NETWORK_TRAFFIC,
            abuse_confidence=AbuseConfidence.HIGH,
            abuse_score=85.0,
            service="auth-svc",
            team="security",
        )
        assert r.credential_name == "cred-stuff-001"
        assert r.abuse_type == AbuseType.BRUTE_FORCE
        assert r.abuse_score == 85.0
        assert r.service == "auth-svc"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_abuse(credential_name=f"abuse-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_abuse(credential_name="test")
        assert eng.get_record(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_record("nonexistent") is None


class TestList:
    def test_list_all(self):
        eng = _engine()
        eng.record_abuse(credential_name="a")
        eng.record_abuse(credential_name="b")
        assert len(eng.list_records()) == 2

    def test_filter_by_abuse_type(self):
        eng = _engine()
        eng.record_abuse(credential_name="a", abuse_type=AbuseType.CREDENTIAL_STUFFING)
        eng.record_abuse(credential_name="b", abuse_type=AbuseType.BRUTE_FORCE)
        assert len(eng.list_records(abuse_type=AbuseType.CREDENTIAL_STUFFING)) == 1

    def test_filter_by_detection_source(self):
        eng = _engine()
        eng.record_abuse(credential_name="a", detection_source=DetectionSource.AUTHENTICATION_LOG)
        eng.record_abuse(credential_name="b", detection_source=DetectionSource.NETWORK_TRAFFIC)
        assert len(eng.list_records(detection_source=DetectionSource.AUTHENTICATION_LOG)) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_abuse(credential_name="a", team="sec")
        eng.record_abuse(credential_name="b", team="ops")
        assert len(eng.list_records(team="sec")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_abuse(credential_name=f"a-{i}")
        assert len(eng.list_records(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            credential_name="test",
            analysis_score=88.5,
            breached=True,
            description="confirmed abuse",
        )
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(credential_name=f"t-{i}")
        assert len(eng._analyses) == 2


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_abuse(
            credential_name="a", abuse_type=AbuseType.CREDENTIAL_STUFFING, abuse_score=90.0
        )
        eng.record_abuse(
            credential_name="b", abuse_type=AbuseType.CREDENTIAL_STUFFING, abuse_score=70.0
        )
        result = eng.analyze_distribution()
        assert "credential_stuffing" in result
        assert result["credential_stuffing"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(threshold=80.0)
        eng.record_abuse(credential_name="a", abuse_score=60.0)
        eng.record_abuse(credential_name="b", abuse_score=90.0)
        assert len(eng.identify_gaps()) == 1

    def test_sorted_ascending(self):
        eng = _engine(threshold=80.0)
        eng.record_abuse(credential_name="a", abuse_score=50.0)
        eng.record_abuse(credential_name="b", abuse_score=30.0)
        results = eng.identify_gaps()
        assert results[0]["abuse_score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_gaps() == []


class TestRankByScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_abuse(credential_name="a", service="auth", abuse_score=90.0)
        eng.record_abuse(credential_name="b", service="api", abuse_score=50.0)
        results = eng.rank_by_score()
        assert results[0]["service"] == "api"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_score() == []


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(credential_name="t", analysis_score=50.0)
        assert eng.detect_trends()["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(credential_name="a", analysis_score=20.0)
        eng.add_analysis(credential_name="b", analysis_score=20.0)
        eng.add_analysis(credential_name="c", analysis_score=80.0)
        eng.add_analysis(credential_name="d", analysis_score=80.0)
        assert eng.detect_trends()["trend"] == "improving"

    def test_insufficient_data(self):
        eng = _engine()
        assert eng.detect_trends()["trend"] == "insufficient_data"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(threshold=80.0)
        eng.record_abuse(credential_name="test", abuse_score=50.0)
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
        eng.record_abuse(credential_name="test")
        eng.add_analysis(credential_name="test")
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
        eng.record_abuse(credential_name="test", service="auth", team="sec")
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
