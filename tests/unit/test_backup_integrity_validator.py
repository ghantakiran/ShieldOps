"""Tests for shieldops.security.backup_integrity_validator — BackupIntegrityValidator."""

from __future__ import annotations

from shieldops.security.backup_integrity_validator import (
    BackupIntegrityAnalysis,
    BackupIntegrityRecord,
    BackupIntegrityReport,
    BackupIntegrityValidator,
    BackupStatus,
    BackupType,
    IntegrityCheck,
)


def _engine(**kw) -> BackupIntegrityValidator:
    return BackupIntegrityValidator(**kw)


class TestEnums:
    def test_e1_v1(self):
        assert BackupType.FULL == "full"

    def test_e1_v2(self):
        assert BackupType.INCREMENTAL == "incremental"

    def test_e1_v3(self):
        assert BackupType.DIFFERENTIAL == "differential"

    def test_e1_v4(self):
        assert BackupType.SNAPSHOT == "snapshot"

    def test_e1_v5(self):
        assert BackupType.CONTINUOUS == "continuous"

    def test_e2_v1(self):
        assert IntegrityCheck.CHECKSUM == "checksum"

    def test_e2_v2(self):
        assert IntegrityCheck.RESTORE_TEST == "restore_test"

    def test_e2_v3(self):
        assert IntegrityCheck.ENCRYPTION_VERIFY == "encryption_verify"

    def test_e2_v4(self):
        assert IntegrityCheck.SIZE_VALIDATION == "size_validation"

    def test_e2_v5(self):
        assert IntegrityCheck.METADATA_CHECK == "metadata_check"

    def test_e3_v1(self):
        assert BackupStatus.VALID == "valid"

    def test_e3_v2(self):
        assert BackupStatus.CORRUPTED == "corrupted"

    def test_e3_v3(self):
        assert BackupStatus.INCOMPLETE == "incomplete"

    def test_e3_v4(self):
        assert BackupStatus.EXPIRED == "expired"

    def test_e3_v5(self):
        assert BackupStatus.UNTESTED == "untested"


class TestModels:
    def test_rec(self):
        r = BackupIntegrityRecord()
        assert r.id and r.integrity_score == 0.0 and r.service == ""

    def test_analysis(self):
        a = BackupIntegrityAnalysis()
        assert a.id and a.analysis_score == 0.0 and a.breached is False

    def test_report(self):
        r = BackupIntegrityReport()
        assert r.id and r.total_records == 0


class TestRecord:
    def test_basic(self):
        r = _engine().record_backup(
            backup_id="t",
            backup_type=BackupType.INCREMENTAL,
            integrity_check=IntegrityCheck.RESTORE_TEST,
            backup_status=BackupStatus.CORRUPTED,
            integrity_score=92.0,
            service="s",
            team="t",
        )
        assert r.backup_id == "t" and r.integrity_score == 92.0

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_backup(backup_id=f"t-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_backup(backup_id="t")
        assert eng.get_backup(r.id) is not None

    def test_not_found(self):
        assert _engine().get_backup("x") is None


class TestList:
    def test_all(self):
        eng = _engine()
        eng.record_backup(backup_id="a")
        eng.record_backup(backup_id="b")
        assert len(eng.list_backups()) == 2

    def test_e1(self):
        eng = _engine()
        eng.record_backup(backup_id="a", backup_type=BackupType.FULL)
        eng.record_backup(backup_id="b", backup_type=BackupType.INCREMENTAL)
        assert len(eng.list_backups(backup_type=BackupType.FULL)) == 1

    def test_e2(self):
        eng = _engine()
        eng.record_backup(backup_id="a", integrity_check=IntegrityCheck.CHECKSUM)
        eng.record_backup(backup_id="b", integrity_check=IntegrityCheck.RESTORE_TEST)
        assert len(eng.list_backups(integrity_check=IntegrityCheck.CHECKSUM)) == 1

    def test_team(self):
        eng = _engine()
        eng.record_backup(backup_id="a", team="x")
        eng.record_backup(backup_id="b", team="y")
        assert len(eng.list_backups(team="x")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_backup(backup_id=f"t-{i}")
        assert len(eng.list_backups(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        a = _engine().add_analysis(
            backup_id="t", backup_type=BackupType.INCREMENTAL, analysis_score=88.5, breached=True
        )
        assert a.analysis_score == 88.5 and a.breached is True

    def test_eviction(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(backup_id=f"t-{i}")
        assert len(eng._analyses) == 2


class TestDistribution:
    def test_data(self):
        eng = _engine()
        eng.record_backup(backup_id="a", backup_type=BackupType.FULL, integrity_score=90.0)
        eng.record_backup(backup_id="b", backup_type=BackupType.FULL, integrity_score=70.0)
        assert "full" in eng.analyze_type_distribution()

    def test_empty(self):
        assert _engine().analyze_type_distribution() == {}


class TestGaps:
    def test_below(self):
        eng = _engine(integrity_threshold=80.0)
        eng.record_backup(backup_id="a", integrity_score=60.0)
        eng.record_backup(backup_id="b", integrity_score=90.0)
        assert len(eng.identify_integrity_gaps()) == 1

    def test_sorted(self):
        eng = _engine(integrity_threshold=80.0)
        eng.record_backup(backup_id="a", integrity_score=50.0)
        eng.record_backup(backup_id="b", integrity_score=30.0)
        assert len(eng.identify_integrity_gaps()) == 2


class TestRank:
    def test_data(self):
        eng = _engine()
        eng.record_backup(backup_id="a", service="s1", integrity_score=80.0)
        eng.record_backup(backup_id="b", service="s2", integrity_score=60.0)
        assert eng.rank_by_integrity()[0]["service"] == "s2"

    def test_empty(self):
        assert _engine().rank_by_integrity() == []


class TestTrends:
    def test_improving(self):
        eng = _engine()
        for v in [10, 20, 30, 40, 50, 60, 70, 80]:
            eng.add_analysis(backup_id="t", analysis_score=float(v))
        assert eng.detect_integrity_trends()["trend"] == "improving"

    def test_stable(self):
        eng = _engine()
        for v in [50, 51, 49, 50]:
            eng.add_analysis(backup_id="t", analysis_score=float(v))
        assert eng.detect_integrity_trends()["trend"] == "stable"

    def test_insufficient(self):
        assert _engine().detect_integrity_trends()["trend"] == "insufficient_data"


class TestReport:
    def test_data(self):
        eng = _engine()
        eng.record_backup(backup_id="t", integrity_score=90.0)
        assert eng.generate_report().total_records == 1

    def test_empty(self):
        assert _engine().generate_report().total_records == 0


class TestClear:
    def test_clears(self):
        eng = _engine()
        eng.record_backup(backup_id="t")
        eng.add_analysis(backup_id="t")
        eng.clear_data()
        assert len(eng._records) == 0 and len(eng._analyses) == 0


class TestStats:
    def test_data(self):
        eng = _engine()
        eng.record_backup(backup_id="t", team="s", service="v")
        assert eng.get_stats()["total_records"] == 1

    def test_empty(self):
        assert _engine().get_stats()["total_records"] == 0

    def test_counts(self):
        eng = _engine()
        eng.record_backup(backup_id="a")
        eng.record_backup(backup_id="b")
        eng.add_analysis(backup_id="t")
        assert eng.get_stats()["total_records"] == 2 and eng.get_stats()["total_analyses"] == 1
