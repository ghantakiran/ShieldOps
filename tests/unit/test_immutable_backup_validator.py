"""Tests for shieldops.security.immutable_backup_validator — ImmutableBackupValidator."""

from __future__ import annotations

from shieldops.security.immutable_backup_validator import (
    ImmutabilityAnalysis,
    ImmutabilityRecord,
    ImmutabilityReport,
    ImmutabilityStatus,
    ImmutabilityType,
    ImmutableBackupValidator,
    ValidationMethod,
)


def _engine(**kw) -> ImmutableBackupValidator:
    return ImmutableBackupValidator(**kw)


class TestEnums:
    def test_e1_v1(self):
        assert ImmutabilityType.WORM == "worm"

    def test_e1_v2(self):
        assert ImmutabilityType.OBJECT_LOCK == "object_lock"

    def test_e1_v3(self):
        assert ImmutabilityType.AIR_GAP == "air_gap"

    def test_e1_v4(self):
        assert ImmutabilityType.BLOCKCHAIN_VERIFIED == "blockchain_verified"

    def test_e1_v5(self):
        assert ImmutabilityType.HARDWARE_ENFORCED == "hardware_enforced"

    def test_e2_v1(self):
        assert ValidationMethod.HASH_VERIFY == "hash_verify"

    def test_e2_v2(self):
        assert ValidationMethod.ACCESS_TEST == "access_test"

    def test_e2_v3(self):
        assert ValidationMethod.RETENTION_CHECK == "retention_check"

    def test_e2_v4(self):
        assert ValidationMethod.TAMPER_DETECT == "tamper_detect"

    def test_e2_v5(self):
        assert ValidationMethod.POLICY_AUDIT == "policy_audit"

    def test_e3_v1(self):
        assert ImmutabilityStatus.IMMUTABLE == "immutable"

    def test_e3_v2(self):
        assert ImmutabilityStatus.MUTABLE == "mutable"

    def test_e3_v3(self):
        assert ImmutabilityStatus.EXPIRED == "expired"

    def test_e3_v4(self):
        assert ImmutabilityStatus.COMPROMISED == "compromised"

    def test_e3_v5(self):
        assert ImmutabilityStatus.UNKNOWN == "unknown"


class TestModels:
    def test_rec(self):
        r = ImmutabilityRecord()
        assert r.id and r.validation_score == 0.0 and r.service == ""

    def test_analysis(self):
        a = ImmutabilityAnalysis()
        assert a.id and a.analysis_score == 0.0 and a.breached is False

    def test_report(self):
        r = ImmutabilityReport()
        assert r.id and r.total_records == 0


class TestRecord:
    def test_basic(self):
        r = _engine().record_immutability(
            immutability_id="t",
            immutability_type=ImmutabilityType.OBJECT_LOCK,
            validation_method=ValidationMethod.ACCESS_TEST,
            immutability_status=ImmutabilityStatus.MUTABLE,
            validation_score=92.0,
            service="s",
            team="t",
        )
        assert r.immutability_id == "t" and r.validation_score == 92.0

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_immutability(immutability_id=f"t-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_immutability(immutability_id="t")
        assert eng.get_immutability(r.id) is not None

    def test_not_found(self):
        assert _engine().get_immutability("x") is None


class TestList:
    def test_all(self):
        eng = _engine()
        eng.record_immutability(immutability_id="a")
        eng.record_immutability(immutability_id="b")
        assert len(eng.list_immutabilities()) == 2

    def test_e1(self):
        eng = _engine()
        eng.record_immutability(immutability_id="a", immutability_type=ImmutabilityType.WORM)
        eng.record_immutability(immutability_id="b", immutability_type=ImmutabilityType.OBJECT_LOCK)
        assert len(eng.list_immutabilities(immutability_type=ImmutabilityType.WORM)) == 1

    def test_e2(self):
        eng = _engine()
        eng.record_immutability(immutability_id="a", validation_method=ValidationMethod.HASH_VERIFY)
        eng.record_immutability(immutability_id="b", validation_method=ValidationMethod.ACCESS_TEST)
        assert len(eng.list_immutabilities(validation_method=ValidationMethod.HASH_VERIFY)) == 1

    def test_team(self):
        eng = _engine()
        eng.record_immutability(immutability_id="a", team="x")
        eng.record_immutability(immutability_id="b", team="y")
        assert len(eng.list_immutabilities(team="x")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_immutability(immutability_id=f"t-{i}")
        assert len(eng.list_immutabilities(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        a = _engine().add_analysis(
            immutability_id="t",
            immutability_type=ImmutabilityType.OBJECT_LOCK,
            analysis_score=88.5,
            breached=True,
        )
        assert a.analysis_score == 88.5 and a.breached is True

    def test_eviction(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(immutability_id=f"t-{i}")
        assert len(eng._analyses) == 2


class TestDistribution:
    def test_data(self):
        eng = _engine()
        eng.record_immutability(
            immutability_id="a", immutability_type=ImmutabilityType.WORM, validation_score=90.0
        )
        eng.record_immutability(
            immutability_id="b", immutability_type=ImmutabilityType.WORM, validation_score=70.0
        )
        assert "worm" in eng.analyze_type_distribution()

    def test_empty(self):
        assert _engine().analyze_type_distribution() == {}


class TestGaps:
    def test_below(self):
        eng = _engine(validation_threshold=80.0)
        eng.record_immutability(immutability_id="a", validation_score=60.0)
        eng.record_immutability(immutability_id="b", validation_score=90.0)
        assert len(eng.identify_validation_gaps()) == 1

    def test_sorted(self):
        eng = _engine(validation_threshold=80.0)
        eng.record_immutability(immutability_id="a", validation_score=50.0)
        eng.record_immutability(immutability_id="b", validation_score=30.0)
        assert len(eng.identify_validation_gaps()) == 2


class TestRank:
    def test_data(self):
        eng = _engine()
        eng.record_immutability(immutability_id="a", service="s1", validation_score=80.0)
        eng.record_immutability(immutability_id="b", service="s2", validation_score=60.0)
        assert eng.rank_by_validation()[0]["service"] == "s2"

    def test_empty(self):
        assert _engine().rank_by_validation() == []


class TestTrends:
    def test_improving(self):
        eng = _engine()
        for v in [10, 20, 30, 40, 50, 60, 70, 80]:
            eng.add_analysis(immutability_id="t", analysis_score=float(v))
        assert eng.detect_validation_trends()["trend"] == "improving"

    def test_stable(self):
        eng = _engine()
        for v in [50, 51, 49, 50]:
            eng.add_analysis(immutability_id="t", analysis_score=float(v))
        assert eng.detect_validation_trends()["trend"] == "stable"

    def test_insufficient(self):
        assert _engine().detect_validation_trends()["trend"] == "insufficient_data"


class TestReport:
    def test_data(self):
        eng = _engine()
        eng.record_immutability(immutability_id="t", validation_score=90.0)
        assert eng.generate_report().total_records == 1

    def test_empty(self):
        assert _engine().generate_report().total_records == 0


class TestClear:
    def test_clears(self):
        eng = _engine()
        eng.record_immutability(immutability_id="t")
        eng.add_analysis(immutability_id="t")
        eng.clear_data()
        assert len(eng._records) == 0 and len(eng._analyses) == 0


class TestStats:
    def test_data(self):
        eng = _engine()
        eng.record_immutability(immutability_id="t", team="s", service="v")
        assert eng.get_stats()["total_records"] == 1

    def test_empty(self):
        assert _engine().get_stats()["total_records"] == 0

    def test_counts(self):
        eng = _engine()
        eng.record_immutability(immutability_id="a")
        eng.record_immutability(immutability_id="b")
        eng.add_analysis(immutability_id="t")
        assert eng.get_stats()["total_records"] == 2 and eng.get_stats()["total_analyses"] == 1
