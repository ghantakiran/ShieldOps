"""Tests for shieldops.security.encryption_key_rotation_monitor — EncryptionKeyRotationMonitor."""

from __future__ import annotations

from shieldops.security.encryption_key_rotation_monitor import (
    EncryptionKeyRotationMonitor,
    KeyRotationAnalysis,
    KeyRotationRecord,
    KeyRotationReport,
    KeyType,
    KeyUsage,
    RotationState,
)


def _engine(**kw) -> EncryptionKeyRotationMonitor:
    return EncryptionKeyRotationMonitor(**kw)


class TestEnums:
    def test_e1_v1(self):
        assert KeyType.AES_256 == "aes_256"

    def test_e1_v2(self):
        assert KeyType.RSA_4096 == "rsa_4096"

    def test_e1_v3(self):
        assert KeyType.ECDSA == "ecdsa"

    def test_e1_v4(self):
        assert KeyType.HMAC == "hmac"

    def test_e1_v5(self):
        assert KeyType.KMS_MANAGED == "kms_managed"

    def test_e2_v1(self):
        assert RotationState.CURRENT == "current"

    def test_e2_v2(self):
        assert RotationState.DUE == "due"

    def test_e2_v3(self):
        assert RotationState.OVERDUE == "overdue"

    def test_e2_v4(self):
        assert RotationState.ROTATING == "rotating"

    def test_e2_v5(self):
        assert RotationState.COMPROMISED == "compromised"

    def test_e3_v1(self):
        assert KeyUsage.ENCRYPTION == "encryption"

    def test_e3_v2(self):
        assert KeyUsage.SIGNING == "signing"

    def test_e3_v3(self):
        assert KeyUsage.AUTHENTICATION == "authentication"

    def test_e3_v4(self):
        assert KeyUsage.KEY_WRAPPING == "key_wrapping"

    def test_e3_v5(self):
        assert KeyUsage.TLS == "tls"


class TestModels:
    def test_rec(self):
        r = KeyRotationRecord()
        assert r.id and r.rotation_score == 0.0 and r.service == ""

    def test_analysis(self):
        a = KeyRotationAnalysis()
        assert a.id and a.analysis_score == 0.0 and a.breached is False

    def test_report(self):
        r = KeyRotationReport()
        assert r.id and r.total_records == 0


class TestRecord:
    def test_basic(self):
        r = _engine().record_rotation(
            rotation_id="t",
            key_type=KeyType.RSA_4096,
            rotation_state=RotationState.DUE,
            key_usage=KeyUsage.SIGNING,
            rotation_score=92.0,
            service="s",
            team="t",
        )
        assert r.rotation_id == "t" and r.rotation_score == 92.0

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_rotation(rotation_id=f"t-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_rotation(rotation_id="t")
        assert eng.get_rotation(r.id) is not None

    def test_not_found(self):
        assert _engine().get_rotation("x") is None


class TestList:
    def test_all(self):
        eng = _engine()
        eng.record_rotation(rotation_id="a")
        eng.record_rotation(rotation_id="b")
        assert len(eng.list_rotations()) == 2

    def test_e1(self):
        eng = _engine()
        eng.record_rotation(rotation_id="a", key_type=KeyType.AES_256)
        eng.record_rotation(rotation_id="b", key_type=KeyType.RSA_4096)
        assert len(eng.list_rotations(key_type=KeyType.AES_256)) == 1

    def test_e2(self):
        eng = _engine()
        eng.record_rotation(rotation_id="a", rotation_state=RotationState.CURRENT)
        eng.record_rotation(rotation_id="b", rotation_state=RotationState.DUE)
        assert len(eng.list_rotations(rotation_state=RotationState.CURRENT)) == 1

    def test_team(self):
        eng = _engine()
        eng.record_rotation(rotation_id="a", team="x")
        eng.record_rotation(rotation_id="b", team="y")
        assert len(eng.list_rotations(team="x")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_rotation(rotation_id=f"t-{i}")
        assert len(eng.list_rotations(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        a = _engine().add_analysis(
            rotation_id="t", key_type=KeyType.RSA_4096, analysis_score=88.5, breached=True
        )
        assert a.analysis_score == 88.5 and a.breached is True

    def test_eviction(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(rotation_id=f"t-{i}")
        assert len(eng._analyses) == 2


class TestDistribution:
    def test_data(self):
        eng = _engine()
        eng.record_rotation(rotation_id="a", key_type=KeyType.AES_256, rotation_score=90.0)
        eng.record_rotation(rotation_id="b", key_type=KeyType.AES_256, rotation_score=70.0)
        assert "aes_256" in eng.analyze_key_type_distribution()

    def test_empty(self):
        assert _engine().analyze_key_type_distribution() == {}


class TestGaps:
    def test_below(self):
        eng = _engine(rotation_threshold=80.0)
        eng.record_rotation(rotation_id="a", rotation_score=60.0)
        eng.record_rotation(rotation_id="b", rotation_score=90.0)
        assert len(eng.identify_rotation_gaps()) == 1

    def test_sorted(self):
        eng = _engine(rotation_threshold=80.0)
        eng.record_rotation(rotation_id="a", rotation_score=50.0)
        eng.record_rotation(rotation_id="b", rotation_score=30.0)
        assert len(eng.identify_rotation_gaps()) == 2


class TestRank:
    def test_data(self):
        eng = _engine()
        eng.record_rotation(rotation_id="a", service="s1", rotation_score=80.0)
        eng.record_rotation(rotation_id="b", service="s2", rotation_score=60.0)
        assert eng.rank_by_rotation()[0]["service"] == "s2"

    def test_empty(self):
        assert _engine().rank_by_rotation() == []


class TestTrends:
    def test_improving(self):
        eng = _engine()
        for v in [10, 20, 30, 40, 50, 60, 70, 80]:
            eng.add_analysis(rotation_id="t", analysis_score=float(v))
        assert eng.detect_rotation_trends()["trend"] == "improving"

    def test_stable(self):
        eng = _engine()
        for v in [50, 51, 49, 50]:
            eng.add_analysis(rotation_id="t", analysis_score=float(v))
        assert eng.detect_rotation_trends()["trend"] == "stable"

    def test_insufficient(self):
        assert _engine().detect_rotation_trends()["trend"] == "insufficient_data"


class TestReport:
    def test_data(self):
        eng = _engine()
        eng.record_rotation(rotation_id="t", rotation_score=90.0)
        assert eng.generate_report().total_records == 1

    def test_empty(self):
        assert _engine().generate_report().total_records == 0


class TestClear:
    def test_clears(self):
        eng = _engine()
        eng.record_rotation(rotation_id="t")
        eng.add_analysis(rotation_id="t")
        eng.clear_data()
        assert len(eng._records) == 0 and len(eng._analyses) == 0


class TestStats:
    def test_data(self):
        eng = _engine()
        eng.record_rotation(rotation_id="t", team="s", service="v")
        assert eng.get_stats()["total_records"] == 1

    def test_empty(self):
        assert _engine().get_stats()["total_records"] == 0

    def test_counts(self):
        eng = _engine()
        eng.record_rotation(rotation_id="a")
        eng.record_rotation(rotation_id="b")
        eng.add_analysis(rotation_id="t")
        assert eng.get_stats()["total_records"] == 2 and eng.get_stats()["total_analyses"] == 1
