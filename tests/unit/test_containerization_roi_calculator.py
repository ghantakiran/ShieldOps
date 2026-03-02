"""Tests for shieldops.billing.containerization_roi_calculator."""

from __future__ import annotations

from shieldops.billing.containerization_roi_calculator import (
    ContainerizationRecord,
    ContainerizationROICalculator,
    ContainerizationROIReport,
    MigrationPhase,
    ROIAnalysis,
    ROICategory,
    WorkloadType,
)


def _engine(**kw) -> ContainerizationROICalculator:
    return ContainerizationROICalculator(**kw)


class TestEnums:
    def test_workloadtype_stateless(self):
        assert WorkloadType.STATELESS == "stateless"

    def test_workloadtype_stateful(self):
        assert WorkloadType.STATEFUL == "stateful"

    def test_workloadtype_batch(self):
        assert WorkloadType.BATCH == "batch"

    def test_workloadtype_streaming(self):
        assert WorkloadType.STREAMING == "streaming"

    def test_workloadtype_ml_training(self):
        assert WorkloadType.ML_TRAINING == "ml_training"

    def test_migrationphase_assessment(self):
        assert MigrationPhase.ASSESSMENT == "assessment"

    def test_migrationphase_containerization(self):
        assert MigrationPhase.CONTAINERIZATION == "containerization"

    def test_migrationphase_optimization(self):
        assert MigrationPhase.OPTIMIZATION == "optimization"

    def test_migrationphase_scaling(self):
        assert MigrationPhase.SCALING == "scaling"

    def test_migrationphase_complete(self):
        assert MigrationPhase.COMPLETE == "complete"

    def test_roicategory_compute_savings(self):
        assert ROICategory.COMPUTE_SAVINGS == "compute_savings"

    def test_roicategory_operational(self):
        assert ROICategory.OPERATIONAL == "operational"

    def test_roicategory_developer_productivity(self):
        assert ROICategory.DEVELOPER_PRODUCTIVITY == "developer_productivity"

    def test_roicategory_scalability(self):
        assert ROICategory.SCALABILITY == "scalability"

    def test_roicategory_resilience(self):
        assert ROICategory.RESILIENCE == "resilience"


class TestModels:
    def test_containerization_record_defaults(self):
        r = ContainerizationRecord()
        assert r.id
        assert r.workload_type == WorkloadType.STATELESS
        assert r.migration_phase == MigrationPhase.ASSESSMENT
        assert r.roi_category == ROICategory.COMPUTE_SAVINGS
        assert r.cost_before == 0.0
        assert r.cost_after == 0.0
        assert r.roi_pct == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_roi_analysis_defaults(self):
        a = ROIAnalysis()
        assert a.id
        assert a.workload_type == WorkloadType.STATELESS
        assert a.analysis_score == 0.0
        assert a.breached is False
        assert a.created_at > 0

    def test_containerization_roi_report_defaults(self):
        r = ContainerizationROIReport()
        assert r.id
        assert r.total_records == 0
        assert r.high_roi_count == 0
        assert r.avg_roi_pct == 0.0
        assert r.by_workload_type == {}
        assert r.top_roi_workloads == []
        assert r.recommendations == []
        assert r.generated_at > 0


class TestRecordROI:
    def test_basic(self):
        eng = _engine()
        r = eng.record_roi(
            workload_type=WorkloadType.BATCH,
            migration_phase=MigrationPhase.COMPLETE,
            roi_category=ROICategory.COMPUTE_SAVINGS,
            cost_before=10000.0,
            cost_after=3000.0,
            roi_pct=70.0,
            service="batch-jobs",
            team="data",
        )
        assert r.workload_type == WorkloadType.BATCH
        assert r.roi_pct == 70.0
        assert r.team == "data"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for _i in range(5):
            eng.record_roi(workload_type=WorkloadType.STATELESS)
        assert len(eng._records) == 3


class TestGetROI:
    def test_found(self):
        eng = _engine()
        r = eng.record_roi(roi_pct=45.0)
        result = eng.get_roi(r.id)
        assert result is not None
        assert result.roi_pct == 45.0

    def test_not_found(self):
        eng = _engine()
        assert eng.get_roi("nonexistent") is None


class TestListROIs:
    def test_list_all(self):
        eng = _engine()
        eng.record_roi(workload_type=WorkloadType.STATELESS)
        eng.record_roi(workload_type=WorkloadType.BATCH)
        assert len(eng.list_rois()) == 2

    def test_filter_by_workload_type(self):
        eng = _engine()
        eng.record_roi(workload_type=WorkloadType.STATELESS)
        eng.record_roi(workload_type=WorkloadType.ML_TRAINING)
        results = eng.list_rois(workload_type=WorkloadType.STATELESS)
        assert len(results) == 1

    def test_filter_by_migration_phase(self):
        eng = _engine()
        eng.record_roi(migration_phase=MigrationPhase.ASSESSMENT)
        eng.record_roi(migration_phase=MigrationPhase.COMPLETE)
        results = eng.list_rois(migration_phase=MigrationPhase.ASSESSMENT)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_roi(team="data")
        eng.record_roi(team="platform")
        results = eng.list_rois(team="data")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for _i in range(10):
            eng.record_roi(workload_type=WorkloadType.STATELESS)
        assert len(eng.list_rois(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            workload_type=WorkloadType.STREAMING,
            analysis_score=88.0,
            threshold=70.0,
            breached=True,
            description="high roi realized",
        )
        assert a.workload_type == WorkloadType.STREAMING
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for _i in range(5):
            eng.add_analysis(workload_type=WorkloadType.STATELESS)
        assert len(eng._analyses) == 2


class TestAnalyzeWorkloadDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_roi(workload_type=WorkloadType.BATCH, roi_pct=60.0)
        eng.record_roi(workload_type=WorkloadType.BATCH, roi_pct=40.0)
        result = eng.analyze_workload_distribution()
        assert "batch" in result
        assert result["batch"]["count"] == 2
        assert result["batch"]["avg_roi_pct"] == 50.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_workload_distribution() == {}


class TestIdentifyHighROIWorkloads:
    def test_detects_above_threshold(self):
        eng = _engine(roi_threshold=30.0)
        eng.record_roi(roi_pct=50.0)
        eng.record_roi(roi_pct=10.0)
        results = eng.identify_high_roi_workloads()
        assert len(results) == 1

    def test_sorted_descending(self):
        eng = _engine(roi_threshold=20.0)
        eng.record_roi(roi_pct=80.0)
        eng.record_roi(roi_pct=40.0)
        results = eng.identify_high_roi_workloads()
        assert results[0]["roi_pct"] == 80.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_high_roi_workloads() == []


class TestRankByROI:
    def test_sorted_descending(self):
        eng = _engine()
        eng.record_roi(service="batch-svc", roi_pct=70.0)
        eng.record_roi(service="web-svc", roi_pct=25.0)
        results = eng.rank_by_roi()
        assert results[0]["service"] == "batch-svc"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_roi() == []


class TestDetectROITrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(analysis_score=50.0)
        result = eng.detect_roi_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(analysis_score=10.0)
        eng.add_analysis(analysis_score=10.0)
        eng.add_analysis(analysis_score=80.0)
        eng.add_analysis(analysis_score=80.0)
        result = eng.detect_roi_trends()
        assert result["trend"] == "improving"

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_roi_trends()
        assert result["trend"] == "insufficient_data"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(roi_threshold=30.0)
        eng.record_roi(
            workload_type=WorkloadType.BATCH,
            migration_phase=MigrationPhase.COMPLETE,
            roi_category=ROICategory.COMPUTE_SAVINGS,
            roi_pct=50.0,
        )
        report = eng.generate_report()
        assert isinstance(report, ContainerizationROIReport)
        assert report.total_records == 1
        assert report.high_roi_count == 1

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "healthy" in report.recommendations[0]


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_roi(workload_type=WorkloadType.BATCH)
        eng.add_analysis(workload_type=WorkloadType.BATCH)
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["workload_type_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_roi(
            workload_type=WorkloadType.BATCH,
            service="batch-jobs",
            team="data",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert "batch" in stats["workload_type_distribution"]
