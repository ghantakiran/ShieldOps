"""Tests for shieldops.security.bulk_export_detector — BulkExportDetector."""

from __future__ import annotations

from shieldops.security.bulk_export_detector import (
    BulkExportAnalysis,
    BulkExportDetector,
    BulkExportRecord,
    BulkExportReport,
    ExportMethod,
    ExportRisk,
    ExportVolume,
)


def _engine(**kw) -> BulkExportDetector:
    return BulkExportDetector(**kw)


class TestEnums:
    def test_e1_v1(self):
        assert ExportMethod.API_BULK == "api_bulk"

    def test_e1_v2(self):
        assert ExportMethod.DATABASE_DUMP == "database_dump"

    def test_e1_v3(self):
        assert ExportMethod.FILE_DOWNLOAD == "file_download"

    def test_e1_v4(self):
        assert ExportMethod.CLOUD_SYNC == "cloud_sync"

    def test_e1_v5(self):
        assert ExportMethod.SCREEN_CAPTURE == "screen_capture"

    def test_e2_v1(self):
        assert ExportVolume.MASSIVE == "massive"

    def test_e2_v2(self):
        assert ExportVolume.LARGE == "large"

    def test_e2_v3(self):
        assert ExportVolume.MEDIUM == "medium"

    def test_e2_v4(self):
        assert ExportVolume.SMALL == "small"

    def test_e2_v5(self):
        assert ExportVolume.NORMAL == "normal"

    def test_e3_v1(self):
        assert ExportRisk.EXFILTRATION == "exfiltration"

    def test_e3_v2(self):
        assert ExportRisk.SUSPICIOUS == "suspicious"

    def test_e3_v3(self):
        assert ExportRisk.ELEVATED == "elevated"

    def test_e3_v4(self):
        assert ExportRisk.NORMAL == "normal"

    def test_e3_v5(self):
        assert ExportRisk.APPROVED == "approved"


class TestModels:
    def test_rec(self):
        r = BulkExportRecord()
        assert r.id and r.export_score == 0.0 and r.service == ""

    def test_analysis(self):
        a = BulkExportAnalysis()
        assert a.id and a.analysis_score == 0.0 and a.breached is False

    def test_report(self):
        r = BulkExportReport()
        assert r.id and r.total_records == 0


class TestRecord:
    def test_basic(self):
        r = _engine().record_export(
            export_id="t",
            export_method=ExportMethod.DATABASE_DUMP,
            export_volume=ExportVolume.LARGE,
            export_risk=ExportRisk.SUSPICIOUS,
            export_score=92.0,
            service="s",
            team="t",
        )
        assert r.export_id == "t" and r.export_score == 92.0

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_export(export_id=f"t-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_export(export_id="t")
        assert eng.get_export(r.id) is not None

    def test_not_found(self):
        assert _engine().get_export("x") is None


class TestList:
    def test_all(self):
        eng = _engine()
        eng.record_export(export_id="a")
        eng.record_export(export_id="b")
        assert len(eng.list_exports()) == 2

    def test_e1(self):
        eng = _engine()
        eng.record_export(export_id="a", export_method=ExportMethod.API_BULK)
        eng.record_export(export_id="b", export_method=ExportMethod.DATABASE_DUMP)
        assert len(eng.list_exports(export_method=ExportMethod.API_BULK)) == 1

    def test_e2(self):
        eng = _engine()
        eng.record_export(export_id="a", export_volume=ExportVolume.MASSIVE)
        eng.record_export(export_id="b", export_volume=ExportVolume.LARGE)
        assert len(eng.list_exports(export_volume=ExportVolume.MASSIVE)) == 1

    def test_team(self):
        eng = _engine()
        eng.record_export(export_id="a", team="x")
        eng.record_export(export_id="b", team="y")
        assert len(eng.list_exports(team="x")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_export(export_id=f"t-{i}")
        assert len(eng.list_exports(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        a = _engine().add_analysis(
            export_id="t",
            export_method=ExportMethod.DATABASE_DUMP,
            analysis_score=88.5,
            breached=True,
        )
        assert a.analysis_score == 88.5 and a.breached is True

    def test_eviction(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(export_id=f"t-{i}")
        assert len(eng._analyses) == 2


class TestDistribution:
    def test_data(self):
        eng = _engine()
        eng.record_export(export_id="a", export_method=ExportMethod.API_BULK, export_score=90.0)
        eng.record_export(export_id="b", export_method=ExportMethod.API_BULK, export_score=70.0)
        assert "api_bulk" in eng.analyze_method_distribution()

    def test_empty(self):
        assert _engine().analyze_method_distribution() == {}


class TestGaps:
    def test_below(self):
        eng = _engine(export_threshold=80.0)
        eng.record_export(export_id="a", export_score=60.0)
        eng.record_export(export_id="b", export_score=90.0)
        assert len(eng.identify_export_gaps()) == 1

    def test_sorted(self):
        eng = _engine(export_threshold=80.0)
        eng.record_export(export_id="a", export_score=50.0)
        eng.record_export(export_id="b", export_score=30.0)
        assert len(eng.identify_export_gaps()) == 2


class TestRank:
    def test_data(self):
        eng = _engine()
        eng.record_export(export_id="a", service="s1", export_score=80.0)
        eng.record_export(export_id="b", service="s2", export_score=60.0)
        assert eng.rank_by_export()[0]["service"] == "s2"

    def test_empty(self):
        assert _engine().rank_by_export() == []


class TestTrends:
    def test_improving(self):
        eng = _engine()
        for v in [10, 20, 30, 40, 50, 60, 70, 80]:
            eng.add_analysis(export_id="t", analysis_score=float(v))
        assert eng.detect_export_trends()["trend"] == "improving"

    def test_stable(self):
        eng = _engine()
        for v in [50, 51, 49, 50]:
            eng.add_analysis(export_id="t", analysis_score=float(v))
        assert eng.detect_export_trends()["trend"] == "stable"

    def test_insufficient(self):
        assert _engine().detect_export_trends()["trend"] == "insufficient_data"


class TestReport:
    def test_data(self):
        eng = _engine()
        eng.record_export(export_id="t", export_score=90.0)
        assert eng.generate_report().total_records == 1

    def test_empty(self):
        assert _engine().generate_report().total_records == 0


class TestClear:
    def test_clears(self):
        eng = _engine()
        eng.record_export(export_id="t")
        eng.add_analysis(export_id="t")
        eng.clear_data()
        assert len(eng._records) == 0 and len(eng._analyses) == 0


class TestStats:
    def test_data(self):
        eng = _engine()
        eng.record_export(export_id="t", team="s", service="v")
        assert eng.get_stats()["total_records"] == 1

    def test_empty(self):
        assert _engine().get_stats()["total_records"] == 0

    def test_counts(self):
        eng = _engine()
        eng.record_export(export_id="a")
        eng.record_export(export_id="b")
        eng.add_analysis(export_id="t")
        assert eng.get_stats()["total_records"] == 2 and eng.get_stats()["total_analyses"] == 1
