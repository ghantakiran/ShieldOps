"""Tests for shieldops.security.sensitive_data_discovery_engine — SensitiveDataDiscoveryEngine."""

from __future__ import annotations

from shieldops.security.sensitive_data_discovery_engine import (
    DataClassification,
    DiscoveryAnalysis,
    DiscoveryMethod,
    DiscoveryRecord,
    DiscoveryReport,
    SensitiveDataDiscoveryEngine,
    StorageLocation,
)


def _engine(**kw) -> SensitiveDataDiscoveryEngine:
    return SensitiveDataDiscoveryEngine(**kw)


class TestEnums:
    def test_e1_v1(self):
        assert DataClassification.TOP_SECRET == "top_secret"  # noqa: S105

    def test_e1_v2(self):
        assert DataClassification.CONFIDENTIAL == "confidential"

    def test_e1_v3(self):
        assert DataClassification.INTERNAL == "internal"

    def test_e1_v4(self):
        assert DataClassification.PUBLIC == "public"

    def test_e1_v5(self):
        assert DataClassification.UNCLASSIFIED == "unclassified"

    def test_e2_v1(self):
        assert DiscoveryMethod.PATTERN_MATCHING == "pattern_matching"

    def test_e2_v2(self):
        assert DiscoveryMethod.ML_CLASSIFICATION == "ml_classification"

    def test_e2_v3(self):
        assert DiscoveryMethod.DLP_SCAN == "dlp_scan"

    def test_e2_v4(self):
        assert DiscoveryMethod.METADATA_ANALYSIS == "metadata_analysis"

    def test_e2_v5(self):
        assert DiscoveryMethod.MANUAL == "manual"

    def test_e3_v1(self):
        assert StorageLocation.DATABASE == "database"

    def test_e3_v2(self):
        assert StorageLocation.FILE_SYSTEM == "file_system"

    def test_e3_v3(self):
        assert StorageLocation.CLOUD_STORAGE == "cloud_storage"

    def test_e3_v4(self):
        assert StorageLocation.API_RESPONSE == "api_response"

    def test_e3_v5(self):
        assert StorageLocation.LOG_FILE == "log_file"


class TestModels:
    def test_rec(self):
        r = DiscoveryRecord()
        assert r.id and r.discovery_score == 0.0 and r.service == ""

    def test_analysis(self):
        a = DiscoveryAnalysis()
        assert a.id and a.analysis_score == 0.0 and a.breached is False

    def test_report(self):
        r = DiscoveryReport()
        assert r.id and r.total_records == 0


class TestRecord:
    def test_basic(self):
        r = _engine().record_discovery(
            discovery_id="t",
            data_classification=DataClassification.CONFIDENTIAL,
            discovery_method=DiscoveryMethod.ML_CLASSIFICATION,
            storage_location=StorageLocation.FILE_SYSTEM,
            discovery_score=92.0,
            service="s",
            team="t",
        )
        assert r.discovery_id == "t" and r.discovery_score == 92.0

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_discovery(discovery_id=f"t-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_discovery(discovery_id="t")
        assert eng.get_discovery(r.id) is not None

    def test_not_found(self):
        assert _engine().get_discovery("x") is None


class TestList:
    def test_all(self):
        eng = _engine()
        eng.record_discovery(discovery_id="a")
        eng.record_discovery(discovery_id="b")
        assert len(eng.list_discoveries()) == 2

    def test_e1(self):
        eng = _engine()
        eng.record_discovery(discovery_id="a", data_classification=DataClassification.TOP_SECRET)
        eng.record_discovery(discovery_id="b", data_classification=DataClassification.CONFIDENTIAL)
        assert len(eng.list_discoveries(data_classification=DataClassification.TOP_SECRET)) == 1

    def test_e2(self):
        eng = _engine()
        eng.record_discovery(discovery_id="a", discovery_method=DiscoveryMethod.PATTERN_MATCHING)
        eng.record_discovery(discovery_id="b", discovery_method=DiscoveryMethod.ML_CLASSIFICATION)
        assert len(eng.list_discoveries(discovery_method=DiscoveryMethod.PATTERN_MATCHING)) == 1

    def test_team(self):
        eng = _engine()
        eng.record_discovery(discovery_id="a", team="x")
        eng.record_discovery(discovery_id="b", team="y")
        assert len(eng.list_discoveries(team="x")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_discovery(discovery_id=f"t-{i}")
        assert len(eng.list_discoveries(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        a = _engine().add_analysis(
            discovery_id="t",
            data_classification=DataClassification.CONFIDENTIAL,
            analysis_score=88.5,
            breached=True,
        )
        assert a.analysis_score == 88.5 and a.breached is True

    def test_eviction(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(discovery_id=f"t-{i}")
        assert len(eng._analyses) == 2


class TestDistribution:
    def test_data(self):
        eng = _engine()
        eng.record_discovery(
            discovery_id="a",
            data_classification=DataClassification.TOP_SECRET,
            discovery_score=90.0,
        )
        eng.record_discovery(
            discovery_id="b",
            data_classification=DataClassification.TOP_SECRET,
            discovery_score=70.0,
        )
        assert "top_secret" in eng.analyze_classification_distribution()

    def test_empty(self):
        assert _engine().analyze_classification_distribution() == {}


class TestGaps:
    def test_below(self):
        eng = _engine(discovery_threshold=80.0)
        eng.record_discovery(discovery_id="a", discovery_score=60.0)
        eng.record_discovery(discovery_id="b", discovery_score=90.0)
        assert len(eng.identify_discovery_gaps()) == 1

    def test_sorted(self):
        eng = _engine(discovery_threshold=80.0)
        eng.record_discovery(discovery_id="a", discovery_score=50.0)
        eng.record_discovery(discovery_id="b", discovery_score=30.0)
        assert len(eng.identify_discovery_gaps()) == 2


class TestRank:
    def test_data(self):
        eng = _engine()
        eng.record_discovery(discovery_id="a", service="s1", discovery_score=80.0)
        eng.record_discovery(discovery_id="b", service="s2", discovery_score=60.0)
        assert eng.rank_by_discovery()[0]["service"] == "s2"

    def test_empty(self):
        assert _engine().rank_by_discovery() == []


class TestTrends:
    def test_improving(self):
        eng = _engine()
        for v in [10, 20, 30, 40, 50, 60, 70, 80]:
            eng.add_analysis(discovery_id="t", analysis_score=float(v))
        assert eng.detect_discovery_trends()["trend"] == "improving"

    def test_stable(self):
        eng = _engine()
        for v in [50, 51, 49, 50]:
            eng.add_analysis(discovery_id="t", analysis_score=float(v))
        assert eng.detect_discovery_trends()["trend"] == "stable"

    def test_insufficient(self):
        assert _engine().detect_discovery_trends()["trend"] == "insufficient_data"


class TestReport:
    def test_data(self):
        eng = _engine()
        eng.record_discovery(discovery_id="t", discovery_score=90.0)
        assert eng.generate_report().total_records == 1

    def test_empty(self):
        assert _engine().generate_report().total_records == 0


class TestClear:
    def test_clears(self):
        eng = _engine()
        eng.record_discovery(discovery_id="t")
        eng.add_analysis(discovery_id="t")
        eng.clear_data()
        assert len(eng._records) == 0 and len(eng._analyses) == 0


class TestStats:
    def test_data(self):
        eng = _engine()
        eng.record_discovery(discovery_id="t", team="s", service="v")
        assert eng.get_stats()["total_records"] == 1

    def test_empty(self):
        assert _engine().get_stats()["total_records"] == 0

    def test_counts(self):
        eng = _engine()
        eng.record_discovery(discovery_id="a")
        eng.record_discovery(discovery_id="b")
        eng.add_analysis(discovery_id="t")
        assert eng.get_stats()["total_records"] == 2 and eng.get_stats()["total_analyses"] == 1
