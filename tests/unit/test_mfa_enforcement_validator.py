"""Tests for shieldops.security.mfa_enforcement_validator — MFAEnforcementValidator."""

from __future__ import annotations

from shieldops.security.mfa_enforcement_validator import (
    ComplianceStatus,
    EnforcementScope,
    MFAAnalysis,
    MFAEnforcementReport,
    MFAEnforcementValidator,
    MFAMethod,
    MFARecord,
)


def _engine(**kw) -> MFAEnforcementValidator:
    return MFAEnforcementValidator(**kw)


class TestEnums:
    def test_e1_v1(self):
        assert MFAMethod.TOTP == "totp"

    def test_e1_v2(self):
        assert MFAMethod.FIDO2 == "fido2"

    def test_e1_v3(self):
        assert MFAMethod.SMS == "sms"

    def test_e1_v4(self):
        assert MFAMethod.PUSH == "push"

    def test_e1_v5(self):
        assert MFAMethod.BIOMETRIC == "biometric"

    def test_e2_v1(self):
        assert EnforcementScope.ALL_USERS == "all_users"

    def test_e2_v2(self):
        assert EnforcementScope.PRIVILEGED == "privileged"

    def test_e2_v3(self):
        assert EnforcementScope.EXTERNAL == "external"

    def test_e2_v4(self):
        assert EnforcementScope.SENSITIVE == "sensitive"

    def test_e2_v5(self):
        assert EnforcementScope.CONDITIONAL == "conditional"

    def test_e3_v1(self):
        assert ComplianceStatus.ENFORCED == "enforced"

    def test_e3_v2(self):
        assert ComplianceStatus.PARTIAL == "partial"

    def test_e3_v3(self):
        assert ComplianceStatus.EXEMPT == "exempt"

    def test_e3_v4(self):
        assert ComplianceStatus.DISABLED == "disabled"

    def test_e3_v5(self):
        assert ComplianceStatus.UNKNOWN == "unknown"


class TestModels:
    def test_rec(self):
        r = MFARecord()
        assert r.id and r.enforcement_score == 0.0 and r.service == ""

    def test_analysis(self):
        a = MFAAnalysis()
        assert a.id and a.analysis_score == 0.0 and a.breached is False

    def test_report(self):
        r = MFAEnforcementReport()
        assert r.id and r.total_records == 0


class TestRecord:
    def test_basic(self):
        r = _engine().record_mfa(
            mfa_id="t",
            mfa_method=MFAMethod.FIDO2,
            enforcement_scope=EnforcementScope.PRIVILEGED,
            compliance_status=ComplianceStatus.PARTIAL,
            enforcement_score=92.0,
            service="s",
            team="t",
        )
        assert r.mfa_id == "t" and r.enforcement_score == 92.0

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_mfa(mfa_id=f"t-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_mfa(mfa_id="t")
        assert eng.get_mfa(r.id) is not None

    def test_not_found(self):
        assert _engine().get_mfa("x") is None


class TestList:
    def test_all(self):
        eng = _engine()
        eng.record_mfa(mfa_id="a")
        eng.record_mfa(mfa_id="b")
        assert len(eng.list_mfas()) == 2

    def test_e1(self):
        eng = _engine()
        eng.record_mfa(mfa_id="a", mfa_method=MFAMethod.TOTP)
        eng.record_mfa(mfa_id="b", mfa_method=MFAMethod.FIDO2)
        assert len(eng.list_mfas(mfa_method=MFAMethod.TOTP)) == 1

    def test_e2(self):
        eng = _engine()
        eng.record_mfa(mfa_id="a", enforcement_scope=EnforcementScope.ALL_USERS)
        eng.record_mfa(mfa_id="b", enforcement_scope=EnforcementScope.PRIVILEGED)
        assert len(eng.list_mfas(enforcement_scope=EnforcementScope.ALL_USERS)) == 1

    def test_team(self):
        eng = _engine()
        eng.record_mfa(mfa_id="a", team="x")
        eng.record_mfa(mfa_id="b", team="y")
        assert len(eng.list_mfas(team="x")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_mfa(mfa_id=f"t-{i}")
        assert len(eng.list_mfas(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        a = _engine().add_analysis(
            mfa_id="t", mfa_method=MFAMethod.FIDO2, analysis_score=88.5, breached=True
        )
        assert a.analysis_score == 88.5 and a.breached is True

    def test_eviction(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(mfa_id=f"t-{i}")
        assert len(eng._analyses) == 2


class TestDistribution:
    def test_data(self):
        eng = _engine()
        eng.record_mfa(mfa_id="a", mfa_method=MFAMethod.TOTP, enforcement_score=90.0)
        eng.record_mfa(mfa_id="b", mfa_method=MFAMethod.TOTP, enforcement_score=70.0)
        assert "totp" in eng.analyze_mfa_distribution()

    def test_empty(self):
        assert _engine().analyze_mfa_distribution() == {}


class TestGaps:
    def test_below(self):
        eng = _engine(enforcement_gap_threshold=80.0)
        eng.record_mfa(mfa_id="a", enforcement_score=60.0)
        eng.record_mfa(mfa_id="b", enforcement_score=90.0)
        assert len(eng.identify_mfa_gaps()) == 1

    def test_sorted(self):
        eng = _engine(enforcement_gap_threshold=80.0)
        eng.record_mfa(mfa_id="a", enforcement_score=50.0)
        eng.record_mfa(mfa_id="b", enforcement_score=30.0)
        assert len(eng.identify_mfa_gaps()) == 2


class TestRank:
    def test_data(self):
        eng = _engine()
        eng.record_mfa(mfa_id="a", service="s1", enforcement_score=80.0)
        eng.record_mfa(mfa_id="b", service="s2", enforcement_score=60.0)
        assert eng.rank_by_mfa()[0]["service"] == "s2"

    def test_empty(self):
        assert _engine().rank_by_mfa() == []


class TestTrends:
    def test_improving(self):
        eng = _engine()
        for v in [10, 20, 30, 40, 50, 60, 70, 80]:
            eng.add_analysis(mfa_id="t", analysis_score=float(v))
        assert eng.detect_mfa_trends()["trend"] == "improving"

    def test_stable(self):
        eng = _engine()
        for v in [50, 51, 49, 50]:
            eng.add_analysis(mfa_id="t", analysis_score=float(v))
        assert eng.detect_mfa_trends()["trend"] == "stable"

    def test_insufficient(self):
        assert _engine().detect_mfa_trends()["trend"] == "insufficient_data"


class TestReport:
    def test_data(self):
        eng = _engine()
        eng.record_mfa(mfa_id="t", enforcement_score=90.0)
        assert eng.generate_report().total_records == 1

    def test_empty(self):
        assert _engine().generate_report().total_records == 0


class TestClear:
    def test_clears(self):
        eng = _engine()
        eng.record_mfa(mfa_id="t")
        eng.add_analysis(mfa_id="t")
        eng.clear_data()
        assert len(eng._records) == 0 and len(eng._analyses) == 0


class TestStats:
    def test_data(self):
        eng = _engine()
        eng.record_mfa(mfa_id="t", team="s", service="v")
        assert eng.get_stats()["total_records"] == 1

    def test_empty(self):
        assert _engine().get_stats()["total_records"] == 0

    def test_counts(self):
        eng = _engine()
        eng.record_mfa(mfa_id="a")
        eng.record_mfa(mfa_id="b")
        eng.add_analysis(mfa_id="t")
        assert eng.get_stats()["total_records"] == 2 and eng.get_stats()["total_analyses"] == 1
