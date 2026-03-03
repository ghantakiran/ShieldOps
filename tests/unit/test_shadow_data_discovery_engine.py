"""Tests for shieldops.security.shadow_data_discovery_engine — ShadowDataDiscoveryEngine."""

from __future__ import annotations

from shieldops.security.shadow_data_discovery_engine import (
    DataRisk,
    DiscoveryStatus,
    ShadowDataAnalysis,
    ShadowDataDiscoveryEngine,
    ShadowDataRecord,
    ShadowDataReport,
    ShadowSource,
)


def _engine(**kw) -> ShadowDataDiscoveryEngine:
    return ShadowDataDiscoveryEngine(**kw)


class TestEnums:
    def test_e1_v1(self):
        assert ShadowSource.PERSONAL_CLOUD == "personal_cloud"

    def test_e1_v2(self):
        assert ShadowSource.SAAS_APP == "saas_app"

    def test_e1_v3(self):
        assert ShadowSource.LOCAL_STORAGE == "local_storage"

    def test_e1_v4(self):
        assert ShadowSource.EMAIL == "email"

    def test_e1_v5(self):
        assert ShadowSource.REMOVABLE_MEDIA == "removable_media"

    def test_e2_v1(self):
        assert DataRisk.REGULATED == "regulated"

    def test_e2_v2(self):
        assert DataRisk.SENSITIVE == "sensitive"

    def test_e2_v3(self):
        assert DataRisk.INTERNAL == "internal"

    def test_e2_v4(self):
        assert DataRisk.LOW_RISK == "low_risk"

    def test_e2_v5(self):
        assert DataRisk.UNKNOWN == "unknown"

    def test_e3_v1(self):
        assert DiscoveryStatus.DISCOVERED == "discovered"

    def test_e3_v2(self):
        assert DiscoveryStatus.CONFIRMED == "confirmed"

    def test_e3_v3(self):
        assert DiscoveryStatus.REMEDIATED == "remediated"

    def test_e3_v4(self):
        assert DiscoveryStatus.ACCEPTED == "accepted"

    def test_e3_v5(self):
        assert DiscoveryStatus.MONITORING == "monitoring"


class TestModels:
    def test_rec(self):
        r = ShadowDataRecord()
        assert r.id and r.discovery_score == 0.0 and r.service == ""

    def test_analysis(self):
        a = ShadowDataAnalysis()
        assert a.id and a.analysis_score == 0.0 and a.breached is False

    def test_report(self):
        r = ShadowDataReport()
        assert r.id and r.total_records == 0


class TestRecord:
    def test_basic(self):
        r = _engine().record_shadow(
            shadow_id="t",
            shadow_source=ShadowSource.SAAS_APP,
            data_risk=DataRisk.SENSITIVE,
            discovery_status=DiscoveryStatus.CONFIRMED,
            discovery_score=92.0,
            service="s",
            team="t",
        )
        assert r.shadow_id == "t" and r.discovery_score == 92.0

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_shadow(shadow_id=f"t-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_shadow(shadow_id="t")
        assert eng.get_shadow(r.id) is not None

    def test_not_found(self):
        assert _engine().get_shadow("x") is None


class TestList:
    def test_all(self):
        eng = _engine()
        eng.record_shadow(shadow_id="a")
        eng.record_shadow(shadow_id="b")
        assert len(eng.list_shadows()) == 2

    def test_e1(self):
        eng = _engine()
        eng.record_shadow(shadow_id="a", shadow_source=ShadowSource.PERSONAL_CLOUD)
        eng.record_shadow(shadow_id="b", shadow_source=ShadowSource.SAAS_APP)
        assert len(eng.list_shadows(shadow_source=ShadowSource.PERSONAL_CLOUD)) == 1

    def test_e2(self):
        eng = _engine()
        eng.record_shadow(shadow_id="a", data_risk=DataRisk.REGULATED)
        eng.record_shadow(shadow_id="b", data_risk=DataRisk.SENSITIVE)
        assert len(eng.list_shadows(data_risk=DataRisk.REGULATED)) == 1

    def test_team(self):
        eng = _engine()
        eng.record_shadow(shadow_id="a", team="x")
        eng.record_shadow(shadow_id="b", team="y")
        assert len(eng.list_shadows(team="x")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_shadow(shadow_id=f"t-{i}")
        assert len(eng.list_shadows(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        a = _engine().add_analysis(
            shadow_id="t", shadow_source=ShadowSource.SAAS_APP, analysis_score=88.5, breached=True
        )
        assert a.analysis_score == 88.5 and a.breached is True

    def test_eviction(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(shadow_id=f"t-{i}")
        assert len(eng._analyses) == 2


class TestDistribution:
    def test_data(self):
        eng = _engine()
        eng.record_shadow(
            shadow_id="a", shadow_source=ShadowSource.PERSONAL_CLOUD, discovery_score=90.0
        )
        eng.record_shadow(
            shadow_id="b", shadow_source=ShadowSource.PERSONAL_CLOUD, discovery_score=70.0
        )
        assert "personal_cloud" in eng.analyze_source_distribution()

    def test_empty(self):
        assert _engine().analyze_source_distribution() == {}


class TestGaps:
    def test_below(self):
        eng = _engine(discovery_threshold=80.0)
        eng.record_shadow(shadow_id="a", discovery_score=60.0)
        eng.record_shadow(shadow_id="b", discovery_score=90.0)
        assert len(eng.identify_shadow_gaps()) == 1

    def test_sorted(self):
        eng = _engine(discovery_threshold=80.0)
        eng.record_shadow(shadow_id="a", discovery_score=50.0)
        eng.record_shadow(shadow_id="b", discovery_score=30.0)
        assert len(eng.identify_shadow_gaps()) == 2


class TestRank:
    def test_data(self):
        eng = _engine()
        eng.record_shadow(shadow_id="a", service="s1", discovery_score=80.0)
        eng.record_shadow(shadow_id="b", service="s2", discovery_score=60.0)
        assert eng.rank_by_shadow()[0]["service"] == "s2"

    def test_empty(self):
        assert _engine().rank_by_shadow() == []


class TestTrends:
    def test_improving(self):
        eng = _engine()
        for v in [10, 20, 30, 40, 50, 60, 70, 80]:
            eng.add_analysis(shadow_id="t", analysis_score=float(v))
        assert eng.detect_shadow_trends()["trend"] == "improving"

    def test_stable(self):
        eng = _engine()
        for v in [50, 51, 49, 50]:
            eng.add_analysis(shadow_id="t", analysis_score=float(v))
        assert eng.detect_shadow_trends()["trend"] == "stable"

    def test_insufficient(self):
        assert _engine().detect_shadow_trends()["trend"] == "insufficient_data"


class TestReport:
    def test_data(self):
        eng = _engine()
        eng.record_shadow(shadow_id="t", discovery_score=90.0)
        assert eng.generate_report().total_records == 1

    def test_empty(self):
        assert _engine().generate_report().total_records == 0


class TestClear:
    def test_clears(self):
        eng = _engine()
        eng.record_shadow(shadow_id="t")
        eng.add_analysis(shadow_id="t")
        eng.clear_data()
        assert len(eng._records) == 0 and len(eng._analyses) == 0


class TestStats:
    def test_data(self):
        eng = _engine()
        eng.record_shadow(shadow_id="t", team="s", service="v")
        assert eng.get_stats()["total_records"] == 1

    def test_empty(self):
        assert _engine().get_stats()["total_records"] == 0

    def test_counts(self):
        eng = _engine()
        eng.record_shadow(shadow_id="a")
        eng.record_shadow(shadow_id="b")
        eng.add_analysis(shadow_id="t")
        assert eng.get_stats()["total_records"] == 2 and eng.get_stats()["total_analyses"] == 1
