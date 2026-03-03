"""Tests for shieldops.security.jit_access_provisioner — JITAccessProvisioner."""

from __future__ import annotations

from shieldops.security.jit_access_provisioner import (
    AccessScope,
    JITAccessProvisioner,
    JITProvisioningReport,
    JustificationType,
    ProvisioningAnalysis,
    ProvisioningRecord,
    ProvisioningStatus,
)


def _engine(**kw) -> JITAccessProvisioner:
    return JITAccessProvisioner(**kw)


class TestEnums:
    def test_e1_v1(self):
        assert AccessScope.READ == "read"

    def test_e1_v2(self):
        assert AccessScope.WRITE == "write"

    def test_e1_v3(self):
        assert AccessScope.ADMIN == "admin"

    def test_e1_v4(self):
        assert AccessScope.EMERGENCY == "emergency"

    def test_e1_v5(self):
        assert AccessScope.CUSTOM == "custom"

    def test_e2_v1(self):
        assert ProvisioningStatus.GRANTED == "granted"

    def test_e2_v2(self):
        assert ProvisioningStatus.PENDING == "pending"

    def test_e2_v3(self):
        assert ProvisioningStatus.DENIED == "denied"

    def test_e2_v4(self):
        assert ProvisioningStatus.EXPIRED == "expired"

    def test_e2_v5(self):
        assert ProvisioningStatus.REVOKED == "revoked"

    def test_e3_v1(self):
        assert JustificationType.INCIDENT == "incident"

    def test_e3_v2(self):
        assert JustificationType.MAINTENANCE == "maintenance"

    def test_e3_v3(self):
        assert JustificationType.AUDIT == "audit"

    def test_e3_v4(self):
        assert JustificationType.DEVELOPMENT == "development"

    def test_e3_v5(self):
        assert JustificationType.ESCALATION == "escalation"


class TestModels:
    def test_rec(self):
        r = ProvisioningRecord()
        assert r.id and r.provisioning_score == 0.0 and r.service == ""

    def test_analysis(self):
        a = ProvisioningAnalysis()
        assert a.id and a.analysis_score == 0.0 and a.breached is False

    def test_report(self):
        r = JITProvisioningReport()
        assert r.id and r.total_records == 0


class TestRecord:
    def test_basic(self):
        r = _engine().record_provisioning(
            provisioning_id="t",
            access_scope=AccessScope.WRITE,
            provisioning_status=ProvisioningStatus.PENDING,
            justification_type=JustificationType.MAINTENANCE,
            provisioning_score=92.0,
            service="s",
            team="t",
        )
        assert r.provisioning_id == "t" and r.provisioning_score == 92.0

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_provisioning(provisioning_id=f"t-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_provisioning(provisioning_id="t")
        assert eng.get_provisioning(r.id) is not None

    def test_not_found(self):
        assert _engine().get_provisioning("x") is None


class TestList:
    def test_all(self):
        eng = _engine()
        eng.record_provisioning(provisioning_id="a")
        eng.record_provisioning(provisioning_id="b")
        assert len(eng.list_provisionings()) == 2

    def test_e1(self):
        eng = _engine()
        eng.record_provisioning(provisioning_id="a", access_scope=AccessScope.READ)
        eng.record_provisioning(provisioning_id="b", access_scope=AccessScope.WRITE)
        assert len(eng.list_provisionings(access_scope=AccessScope.READ)) == 1

    def test_e2(self):
        eng = _engine()
        eng.record_provisioning(provisioning_id="a", provisioning_status=ProvisioningStatus.GRANTED)
        eng.record_provisioning(provisioning_id="b", provisioning_status=ProvisioningStatus.PENDING)
        assert len(eng.list_provisionings(provisioning_status=ProvisioningStatus.GRANTED)) == 1

    def test_team(self):
        eng = _engine()
        eng.record_provisioning(provisioning_id="a", team="x")
        eng.record_provisioning(provisioning_id="b", team="y")
        assert len(eng.list_provisionings(team="x")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_provisioning(provisioning_id=f"t-{i}")
        assert len(eng.list_provisionings(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        a = _engine().add_analysis(
            provisioning_id="t", access_scope=AccessScope.WRITE, analysis_score=88.5, breached=True
        )
        assert a.analysis_score == 88.5 and a.breached is True

    def test_eviction(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(provisioning_id=f"t-{i}")
        assert len(eng._analyses) == 2


class TestDistribution:
    def test_data(self):
        eng = _engine()
        eng.record_provisioning(
            provisioning_id="a", access_scope=AccessScope.READ, provisioning_score=90.0
        )
        eng.record_provisioning(
            provisioning_id="b", access_scope=AccessScope.READ, provisioning_score=70.0
        )
        assert "read" in eng.analyze_provisioning_distribution()

    def test_empty(self):
        assert _engine().analyze_provisioning_distribution() == {}


class TestGaps:
    def test_below(self):
        eng = _engine(provisioning_gap_threshold=80.0)
        eng.record_provisioning(provisioning_id="a", provisioning_score=60.0)
        eng.record_provisioning(provisioning_id="b", provisioning_score=90.0)
        assert len(eng.identify_provisioning_gaps()) == 1

    def test_sorted(self):
        eng = _engine(provisioning_gap_threshold=80.0)
        eng.record_provisioning(provisioning_id="a", provisioning_score=50.0)
        eng.record_provisioning(provisioning_id="b", provisioning_score=30.0)
        assert len(eng.identify_provisioning_gaps()) == 2


class TestRank:
    def test_data(self):
        eng = _engine()
        eng.record_provisioning(provisioning_id="a", service="s1", provisioning_score=80.0)
        eng.record_provisioning(provisioning_id="b", service="s2", provisioning_score=60.0)
        assert eng.rank_by_provisioning()[0]["service"] == "s2"

    def test_empty(self):
        assert _engine().rank_by_provisioning() == []


class TestTrends:
    def test_improving(self):
        eng = _engine()
        for v in [10, 20, 30, 40, 50, 60, 70, 80]:
            eng.add_analysis(provisioning_id="t", analysis_score=float(v))
        assert eng.detect_provisioning_trends()["trend"] == "improving"

    def test_stable(self):
        eng = _engine()
        for v in [50, 51, 49, 50]:
            eng.add_analysis(provisioning_id="t", analysis_score=float(v))
        assert eng.detect_provisioning_trends()["trend"] == "stable"

    def test_insufficient(self):
        assert _engine().detect_provisioning_trends()["trend"] == "insufficient_data"


class TestReport:
    def test_data(self):
        eng = _engine()
        eng.record_provisioning(provisioning_id="t", provisioning_score=90.0)
        assert eng.generate_report().total_records == 1

    def test_empty(self):
        assert _engine().generate_report().total_records == 0


class TestClear:
    def test_clears(self):
        eng = _engine()
        eng.record_provisioning(provisioning_id="t")
        eng.add_analysis(provisioning_id="t")
        eng.clear_data()
        assert len(eng._records) == 0 and len(eng._analyses) == 0


class TestStats:
    def test_data(self):
        eng = _engine()
        eng.record_provisioning(provisioning_id="t", team="s", service="v")
        assert eng.get_stats()["total_records"] == 1

    def test_empty(self):
        assert _engine().get_stats()["total_records"] == 0

    def test_counts(self):
        eng = _engine()
        eng.record_provisioning(provisioning_id="a")
        eng.record_provisioning(provisioning_id="b")
        eng.add_analysis(provisioning_id="t")
        assert eng.get_stats()["total_records"] == 2 and eng.get_stats()["total_analyses"] == 1
