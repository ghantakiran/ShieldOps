"""Tests for shieldops.security.identity_federation_monitor — IdentityFederationMonitor."""

from __future__ import annotations

from shieldops.security.identity_federation_monitor import (
    FederationAnalysis,
    FederationHealth,
    FederationProtocol,
    FederationRecord,
    IdentityFederationMonitor,
    IdentityFederationReport,
    MonitoringEvent,
)


def _engine(**kw) -> IdentityFederationMonitor:
    return IdentityFederationMonitor(**kw)


class TestEnums:
    def test_e1_v1(self):
        assert FederationProtocol.SAML == "saml"

    def test_e1_v2(self):
        assert FederationProtocol.OIDC == "oidc"

    def test_e1_v3(self):
        assert FederationProtocol.OAUTH2 == "oauth2"

    def test_e1_v4(self):
        assert FederationProtocol.SCIM == "scim"

    def test_e1_v5(self):
        assert FederationProtocol.LDAP == "ldap"

    def test_e2_v1(self):
        assert MonitoringEvent.TOKEN_ISSUE == "token_issue"  # noqa: S105

    def test_e2_v2(self):
        assert MonitoringEvent.TOKEN_REFRESH == "token_refresh"  # noqa: S105

    def test_e2_v3(self):
        assert MonitoringEvent.TOKEN_REVOKE == "token_revoke"  # noqa: S105

    def test_e2_v4(self):
        assert MonitoringEvent.FEDERATION_SYNC == "federation_sync"

    def test_e2_v5(self):
        assert MonitoringEvent.FEDERATION_ERROR == "federation_error"

    def test_e3_v1(self):
        assert FederationHealth.HEALTHY == "healthy"

    def test_e3_v2(self):
        assert FederationHealth.DEGRADED == "degraded"

    def test_e3_v3(self):
        assert FederationHealth.IMPAIRED == "impaired"

    def test_e3_v4(self):
        assert FederationHealth.DOWN == "down"

    def test_e3_v5(self):
        assert FederationHealth.UNKNOWN == "unknown"


class TestModels:
    def test_rec(self):
        r = FederationRecord()
        assert r.id and r.health_score == 0.0 and r.service == ""

    def test_analysis(self):
        a = FederationAnalysis()
        assert a.id and a.analysis_score == 0.0 and a.breached is False

    def test_report(self):
        r = IdentityFederationReport()
        assert r.id and r.total_records == 0


class TestRecord:
    def test_basic(self):
        r = _engine().record_federation(
            federation_id="t",
            federation_protocol=FederationProtocol.OIDC,
            monitoring_event=MonitoringEvent.TOKEN_REFRESH,
            federation_health=FederationHealth.DEGRADED,
            health_score=92.0,
            service="s",
            team="t",
        )
        assert r.federation_id == "t" and r.health_score == 92.0

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_federation(federation_id=f"t-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_federation(federation_id="t")
        assert eng.get_federation(r.id) is not None

    def test_not_found(self):
        assert _engine().get_federation("x") is None


class TestList:
    def test_all(self):
        eng = _engine()
        eng.record_federation(federation_id="a")
        eng.record_federation(federation_id="b")
        assert len(eng.list_federations()) == 2

    def test_e1(self):
        eng = _engine()
        eng.record_federation(federation_id="a", federation_protocol=FederationProtocol.SAML)
        eng.record_federation(federation_id="b", federation_protocol=FederationProtocol.OIDC)
        assert len(eng.list_federations(federation_protocol=FederationProtocol.SAML)) == 1

    def test_e2(self):
        eng = _engine()
        eng.record_federation(federation_id="a", monitoring_event=MonitoringEvent.TOKEN_ISSUE)
        eng.record_federation(federation_id="b", monitoring_event=MonitoringEvent.TOKEN_REFRESH)
        assert len(eng.list_federations(monitoring_event=MonitoringEvent.TOKEN_ISSUE)) == 1

    def test_team(self):
        eng = _engine()
        eng.record_federation(federation_id="a", team="x")
        eng.record_federation(federation_id="b", team="y")
        assert len(eng.list_federations(team="x")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_federation(federation_id=f"t-{i}")
        assert len(eng.list_federations(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        a = _engine().add_analysis(
            federation_id="t",
            federation_protocol=FederationProtocol.OIDC,
            analysis_score=88.5,
            breached=True,
        )
        assert a.analysis_score == 88.5 and a.breached is True

    def test_eviction(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(federation_id=f"t-{i}")
        assert len(eng._analyses) == 2


class TestDistribution:
    def test_data(self):
        eng = _engine()
        eng.record_federation(
            federation_id="a", federation_protocol=FederationProtocol.SAML, health_score=90.0
        )
        eng.record_federation(
            federation_id="b", federation_protocol=FederationProtocol.SAML, health_score=70.0
        )
        assert "saml" in eng.analyze_federation_distribution()

    def test_empty(self):
        assert _engine().analyze_federation_distribution() == {}


class TestGaps:
    def test_below(self):
        eng = _engine(federation_gap_threshold=80.0)
        eng.record_federation(federation_id="a", health_score=60.0)
        eng.record_federation(federation_id="b", health_score=90.0)
        assert len(eng.identify_federation_gaps()) == 1

    def test_sorted(self):
        eng = _engine(federation_gap_threshold=80.0)
        eng.record_federation(federation_id="a", health_score=50.0)
        eng.record_federation(federation_id="b", health_score=30.0)
        assert len(eng.identify_federation_gaps()) == 2


class TestRank:
    def test_data(self):
        eng = _engine()
        eng.record_federation(federation_id="a", service="s1", health_score=80.0)
        eng.record_federation(federation_id="b", service="s2", health_score=60.0)
        assert eng.rank_by_federation()[0]["service"] == "s2"

    def test_empty(self):
        assert _engine().rank_by_federation() == []


class TestTrends:
    def test_improving(self):
        eng = _engine()
        for v in [10, 20, 30, 40, 50, 60, 70, 80]:
            eng.add_analysis(federation_id="t", analysis_score=float(v))
        assert eng.detect_federation_trends()["trend"] == "improving"

    def test_stable(self):
        eng = _engine()
        for v in [50, 51, 49, 50]:
            eng.add_analysis(federation_id="t", analysis_score=float(v))
        assert eng.detect_federation_trends()["trend"] == "stable"

    def test_insufficient(self):
        assert _engine().detect_federation_trends()["trend"] == "insufficient_data"


class TestReport:
    def test_data(self):
        eng = _engine()
        eng.record_federation(federation_id="t", health_score=90.0)
        assert eng.generate_report().total_records == 1

    def test_empty(self):
        assert _engine().generate_report().total_records == 0


class TestClear:
    def test_clears(self):
        eng = _engine()
        eng.record_federation(federation_id="t")
        eng.add_analysis(federation_id="t")
        eng.clear_data()
        assert len(eng._records) == 0 and len(eng._analyses) == 0


class TestStats:
    def test_data(self):
        eng = _engine()
        eng.record_federation(federation_id="t", team="s", service="v")
        assert eng.get_stats()["total_records"] == 1

    def test_empty(self):
        assert _engine().get_stats()["total_records"] == 0

    def test_counts(self):
        eng = _engine()
        eng.record_federation(federation_id="a")
        eng.record_federation(federation_id="b")
        eng.add_analysis(federation_id="t")
        assert eng.get_stats()["total_records"] == 2 and eng.get_stats()["total_analyses"] == 1
