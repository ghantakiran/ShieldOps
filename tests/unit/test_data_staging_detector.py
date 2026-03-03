"""Tests for shieldops.security.data_staging_detector — DataStagingDetector."""

from __future__ import annotations

from shieldops.security.data_staging_detector import (
    DataStagingDetector,
    DataStagingReport,
    DataType,
    StagingAnalysis,
    StagingIndicator,
    StagingMethod,
    StagingRecord,
)


def _engine(**kw) -> DataStagingDetector:
    return DataStagingDetector(**kw)


class TestEnums:
    def test_e1_v1(self):
        assert StagingMethod.COMPRESSION == "compression"

    def test_e1_v2(self):
        assert StagingMethod.ENCRYPTION == "encryption"

    def test_e1_v3(self):
        assert StagingMethod.DIRECTORY_COLLECTION == "directory_collection"

    def test_e1_v4(self):
        assert StagingMethod.CLOUD_STAGING == "cloud_staging"

    def test_e1_v5(self):
        assert StagingMethod.TEMP_STORAGE == "temp_storage"

    def test_e2_v1(self):
        assert DataType.PII == "pii"

    def test_e2_v2(self):
        assert DataType.FINANCIAL == "financial"

    def test_e2_v3(self):
        assert DataType.INTELLECTUAL_PROPERTY == "intellectual_property"

    def test_e2_v4(self):
        assert DataType.CREDENTIALS == "credentials"  # noqa: S105

    def test_e2_v5(self):
        assert DataType.CONFIGURATION == "configuration"

    def test_e3_v1(self):
        assert StagingIndicator.CONFIRMED == "confirmed"

    def test_e3_v2(self):
        assert StagingIndicator.SUSPICIOUS == "suspicious"

    def test_e3_v3(self):
        assert StagingIndicator.ELEVATED == "elevated"

    def test_e3_v4(self):
        assert StagingIndicator.NORMAL == "normal"

    def test_e3_v5(self):
        assert StagingIndicator.FALSE_POSITIVE == "false_positive"


class TestModels:
    def test_rec(self):
        r = StagingRecord()
        assert r.id and r.detection_score == 0.0 and r.service == ""

    def test_analysis(self):
        a = StagingAnalysis()
        assert a.id and a.analysis_score == 0.0 and a.breached is False

    def test_report(self):
        r = DataStagingReport()
        assert r.id and r.total_records == 0


class TestRecord:
    def test_basic(self):
        r = _engine().record_staging(
            staging_id="t",
            staging_method=StagingMethod.ENCRYPTION,
            data_type=DataType.FINANCIAL,
            staging_indicator=StagingIndicator.SUSPICIOUS,
            detection_score=92.0,
            service="s",
            team="t",
        )
        assert r.staging_id == "t" and r.detection_score == 92.0

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_staging(staging_id=f"t-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_staging(staging_id="t")
        assert eng.get_staging(r.id) is not None

    def test_not_found(self):
        assert _engine().get_staging("x") is None


class TestList:
    def test_all(self):
        eng = _engine()
        eng.record_staging(staging_id="a")
        eng.record_staging(staging_id="b")
        assert len(eng.list_stagings()) == 2

    def test_e1(self):
        eng = _engine()
        eng.record_staging(staging_id="a", staging_method=StagingMethod.COMPRESSION)
        eng.record_staging(staging_id="b", staging_method=StagingMethod.ENCRYPTION)
        assert len(eng.list_stagings(staging_method=StagingMethod.COMPRESSION)) == 1

    def test_e2(self):
        eng = _engine()
        eng.record_staging(staging_id="a", data_type=DataType.PII)
        eng.record_staging(staging_id="b", data_type=DataType.FINANCIAL)
        assert len(eng.list_stagings(data_type=DataType.PII)) == 1

    def test_team(self):
        eng = _engine()
        eng.record_staging(staging_id="a", team="x")
        eng.record_staging(staging_id="b", team="y")
        assert len(eng.list_stagings(team="x")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_staging(staging_id=f"t-{i}")
        assert len(eng.list_stagings(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        a = _engine().add_analysis(
            staging_id="t",
            staging_method=StagingMethod.ENCRYPTION,
            analysis_score=88.5,
            breached=True,
        )
        assert a.analysis_score == 88.5 and a.breached is True

    def test_eviction(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(staging_id=f"t-{i}")
        assert len(eng._analyses) == 2


class TestDistribution:
    def test_data(self):
        eng = _engine()
        eng.record_staging(
            staging_id="a", staging_method=StagingMethod.COMPRESSION, detection_score=90.0
        )
        eng.record_staging(
            staging_id="b", staging_method=StagingMethod.COMPRESSION, detection_score=70.0
        )
        assert "compression" in eng.analyze_method_distribution()

    def test_empty(self):
        assert _engine().analyze_method_distribution() == {}


class TestGaps:
    def test_below(self):
        eng = _engine(detection_threshold=80.0)
        eng.record_staging(staging_id="a", detection_score=60.0)
        eng.record_staging(staging_id="b", detection_score=90.0)
        assert len(eng.identify_detection_gaps()) == 1

    def test_sorted(self):
        eng = _engine(detection_threshold=80.0)
        eng.record_staging(staging_id="a", detection_score=50.0)
        eng.record_staging(staging_id="b", detection_score=30.0)
        assert len(eng.identify_detection_gaps()) == 2


class TestRank:
    def test_data(self):
        eng = _engine()
        eng.record_staging(staging_id="a", service="s1", detection_score=80.0)
        eng.record_staging(staging_id="b", service="s2", detection_score=60.0)
        assert eng.rank_by_detection()[0]["service"] == "s2"

    def test_empty(self):
        assert _engine().rank_by_detection() == []


class TestTrends:
    def test_improving(self):
        eng = _engine()
        for v in [10, 20, 30, 40, 50, 60, 70, 80]:
            eng.add_analysis(staging_id="t", analysis_score=float(v))
        assert eng.detect_detection_trends()["trend"] == "improving"

    def test_stable(self):
        eng = _engine()
        for v in [50, 51, 49, 50]:
            eng.add_analysis(staging_id="t", analysis_score=float(v))
        assert eng.detect_detection_trends()["trend"] == "stable"

    def test_insufficient(self):
        assert _engine().detect_detection_trends()["trend"] == "insufficient_data"


class TestReport:
    def test_data(self):
        eng = _engine()
        eng.record_staging(staging_id="t", detection_score=90.0)
        assert eng.generate_report().total_records == 1

    def test_empty(self):
        assert _engine().generate_report().total_records == 0


class TestClear:
    def test_clears(self):
        eng = _engine()
        eng.record_staging(staging_id="t")
        eng.add_analysis(staging_id="t")
        eng.clear_data()
        assert len(eng._records) == 0 and len(eng._analyses) == 0


class TestStats:
    def test_data(self):
        eng = _engine()
        eng.record_staging(staging_id="t", team="s", service="v")
        assert eng.get_stats()["total_records"] == 1

    def test_empty(self):
        assert _engine().get_stats()["total_records"] == 0

    def test_counts(self):
        eng = _engine()
        eng.record_staging(staging_id="a")
        eng.record_staging(staging_id="b")
        eng.add_analysis(staging_id="t")
        assert eng.get_stats()["total_records"] == 2 and eng.get_stats()["total_analyses"] == 1
