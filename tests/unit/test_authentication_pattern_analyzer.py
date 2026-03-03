"""Tests for shieldops.analytics.authentication_pattern_analyzer — AuthenticationPatternAnalyzer."""

from __future__ import annotations

from shieldops.analytics.authentication_pattern_analyzer import (
    AuthenticationPatternAnalyzer,
    AuthMethod,
    AuthPatternAnalysis,
    AuthPatternRecord,
    AuthPatternReport,
    PatternStatus,
    PatternType,
)


def _engine(**kw) -> AuthenticationPatternAnalyzer:
    return AuthenticationPatternAnalyzer(**kw)


class TestEnums:
    def test_method_password(self):
        assert AuthMethod.PASSWORD == "password"  # noqa: S105

    def test_method_mfa(self):
        assert AuthMethod.MFA == "mfa"

    def test_method_sso(self):
        assert AuthMethod.SSO == "sso"

    def test_method_certificate(self):
        assert AuthMethod.CERTIFICATE == "certificate"

    def test_method_biometric(self):
        assert AuthMethod.BIOMETRIC == "biometric"

    def test_pattern_login_time(self):
        assert PatternType.LOGIN_TIME == "login_time"

    def test_pattern_location(self):
        assert PatternType.LOCATION == "location"

    def test_pattern_device(self):
        assert PatternType.DEVICE == "device"

    def test_pattern_failure_rate(self):
        assert PatternType.FAILURE_RATE == "failure_rate"

    def test_pattern_session_duration(self):
        assert PatternType.SESSION_DURATION == "session_duration"

    def test_status_normal(self):
        assert PatternStatus.NORMAL == "normal"

    def test_status_unusual(self):
        assert PatternStatus.UNUSUAL == "unusual"

    def test_status_suspicious(self):
        assert PatternStatus.SUSPICIOUS == "suspicious"

    def test_status_anomalous(self):
        assert PatternStatus.ANOMALOUS == "anomalous"

    def test_status_blocked(self):
        assert PatternStatus.BLOCKED == "blocked"


class TestModels:
    def test_record_defaults(self):
        r = AuthPatternRecord()
        assert r.id
        assert r.user_name == ""
        assert r.auth_method == AuthMethod.PASSWORD
        assert r.pattern_type == PatternType.LOGIN_TIME
        assert r.pattern_status == PatternStatus.NORMAL
        assert r.pattern_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_analysis_defaults(self):
        a = AuthPatternAnalysis()
        assert a.id
        assert a.user_name == ""
        assert a.auth_method == AuthMethod.PASSWORD
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = AuthPatternReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_pattern_score == 0.0
        assert r.by_auth_method == {}
        assert r.by_pattern_type == {}
        assert r.by_pattern_status == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_pattern(
            user_name="travel-anomaly",
            auth_method=AuthMethod.SSO,
            pattern_type=PatternType.LOCATION,
            pattern_status=PatternStatus.SUSPICIOUS,
            pattern_score=85.0,
            service="idp-svc",
            team="security",
        )
        assert r.user_name == "travel-anomaly"
        assert r.auth_method == AuthMethod.SSO
        assert r.pattern_score == 85.0
        assert r.service == "idp-svc"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_pattern(user_name=f"pat-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_pattern(user_name="test")
        assert eng.get_record(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_record("nonexistent") is None


class TestList:
    def test_list_all(self):
        eng = _engine()
        eng.record_pattern(user_name="a")
        eng.record_pattern(user_name="b")
        assert len(eng.list_records()) == 2

    def test_filter_by_auth_method(self):
        eng = _engine()
        eng.record_pattern(user_name="a", auth_method=AuthMethod.PASSWORD)
        eng.record_pattern(user_name="b", auth_method=AuthMethod.MFA)
        assert len(eng.list_records(auth_method=AuthMethod.PASSWORD)) == 1

    def test_filter_by_pattern_type(self):
        eng = _engine()
        eng.record_pattern(user_name="a", pattern_type=PatternType.LOGIN_TIME)
        eng.record_pattern(user_name="b", pattern_type=PatternType.LOCATION)
        assert len(eng.list_records(pattern_type=PatternType.LOGIN_TIME)) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_pattern(user_name="a", team="sec")
        eng.record_pattern(user_name="b", team="ops")
        assert len(eng.list_records(team="sec")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_pattern(user_name=f"p-{i}")
        assert len(eng.list_records(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            user_name="test",
            analysis_score=88.5,
            breached=True,
            description="impossible travel",
        )
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(user_name=f"t-{i}")
        assert len(eng._analyses) == 2


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_pattern(user_name="a", auth_method=AuthMethod.PASSWORD, pattern_score=90.0)
        eng.record_pattern(user_name="b", auth_method=AuthMethod.PASSWORD, pattern_score=70.0)
        result = eng.analyze_distribution()
        assert "password" in result
        assert result["password"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(threshold=80.0)
        eng.record_pattern(user_name="a", pattern_score=60.0)
        eng.record_pattern(user_name="b", pattern_score=90.0)
        assert len(eng.identify_gaps()) == 1

    def test_sorted_ascending(self):
        eng = _engine(threshold=80.0)
        eng.record_pattern(user_name="a", pattern_score=50.0)
        eng.record_pattern(user_name="b", pattern_score=30.0)
        results = eng.identify_gaps()
        assert results[0]["pattern_score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_gaps() == []


class TestRankByScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_pattern(user_name="a", service="auth", pattern_score=90.0)
        eng.record_pattern(user_name="b", service="api", pattern_score=50.0)
        results = eng.rank_by_score()
        assert results[0]["service"] == "api"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_score() == []


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(user_name="t", analysis_score=50.0)
        assert eng.detect_trends()["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(user_name="a", analysis_score=20.0)
        eng.add_analysis(user_name="b", analysis_score=20.0)
        eng.add_analysis(user_name="c", analysis_score=80.0)
        eng.add_analysis(user_name="d", analysis_score=80.0)
        assert eng.detect_trends()["trend"] == "improving"

    def test_insufficient_data(self):
        eng = _engine()
        assert eng.detect_trends()["trend"] == "insufficient_data"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(threshold=80.0)
        eng.record_pattern(user_name="test", pattern_score=50.0)
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
        eng.record_pattern(user_name="test")
        eng.add_analysis(user_name="test")
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
        eng.record_pattern(user_name="test", service="auth", team="sec")
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
