"""Tests for shieldops.observability.chaos_designer — ChaosExperimentDesigner.

Covers ExperimentType, BlastRadiusLevel, and ExperimentStatus enums,
ExperimentDesign / PrerequisiteCheck / ChaosDesignReport models, and all
ChaosExperimentDesigner operations including experiment creation, blast radius
estimation, prerequisite validation, rollback plan generation, approval,
coverage analysis, and report generation.
"""

from __future__ import annotations

from shieldops.observability.chaos_designer import (
    BlastRadiusLevel,
    ChaosDesignReport,
    ChaosExperimentDesigner,
    ExperimentDesign,
    ExperimentStatus,
    ExperimentType,
    PrerequisiteCheck,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _engine(**kw) -> ChaosExperimentDesigner:
    return ChaosExperimentDesigner(**kw)


# ===========================================================================
# Enum tests
# ===========================================================================


class TestEnums:
    """Validate every member of ExperimentType, BlastRadiusLevel, and ExperimentStatus."""

    # -- ExperimentType (5 members) -------------------------------------------

    def test_type_network_partition(self):
        assert ExperimentType.NETWORK_PARTITION == "network_partition"

    def test_type_resource_exhaustion(self):
        assert ExperimentType.RESOURCE_EXHAUSTION == "resource_exhaustion"

    def test_type_service_kill(self):
        assert ExperimentType.SERVICE_KILL == "service_kill"

    def test_type_latency_injection(self):
        assert ExperimentType.LATENCY_INJECTION == "latency_injection"

    def test_type_dependency_failure(self):
        assert ExperimentType.DEPENDENCY_FAILURE == "dependency_failure"

    # -- BlastRadiusLevel (5 members) -----------------------------------------

    def test_blast_minimal(self):
        assert BlastRadiusLevel.MINIMAL == "minimal"

    def test_blast_contained(self):
        assert BlastRadiusLevel.CONTAINED == "contained"

    def test_blast_moderate(self):
        assert BlastRadiusLevel.MODERATE == "moderate"

    def test_blast_significant(self):
        assert BlastRadiusLevel.SIGNIFICANT == "significant"

    def test_blast_catastrophic(self):
        assert BlastRadiusLevel.CATASTROPHIC == "catastrophic"

    # -- ExperimentStatus (5 members) -----------------------------------------

    def test_status_draft(self):
        assert ExperimentStatus.DRAFT == "draft"

    def test_status_approved(self):
        assert ExperimentStatus.APPROVED == "approved"

    def test_status_scheduled(self):
        assert ExperimentStatus.SCHEDULED == "scheduled"

    def test_status_running(self):
        assert ExperimentStatus.RUNNING == "running"

    def test_status_completed(self):
        assert ExperimentStatus.COMPLETED == "completed"


# ===========================================================================
# Model defaults
# ===========================================================================


class TestModels:
    """Verify default field values for each Pydantic model."""

    def test_experiment_design_defaults(self):
        e = ExperimentDesign()
        assert e.id
        assert e.name == ""
        assert e.experiment_type == ExperimentType.NETWORK_PARTITION
        assert e.target_service == ""
        assert e.blast_radius_level == BlastRadiusLevel.MINIMAL
        assert e.status == ExperimentStatus.DRAFT
        assert e.hypothesis == ""
        assert e.rollback_plan == ""
        assert e.prerequisites == []
        assert e.affected_services == []
        assert e.estimated_duration_minutes == 30
        assert e.created_at > 0

    def test_prerequisite_check_defaults(self):
        p = PrerequisiteCheck()
        assert p.id
        assert p.experiment_id == ""
        assert p.check_name == ""
        assert p.passed is False
        assert p.details == ""
        assert p.checked_at > 0

    def test_chaos_design_report_defaults(self):
        r = ChaosDesignReport()
        assert r.total_experiments == 0
        assert r.by_type == {}
        assert r.by_status == {}
        assert r.avg_blast_radius == 0.0
        assert r.coverage_pct == 0.0
        assert r.recommendations == []
        assert r.generated_at > 0


# ===========================================================================
# CreateExperiment
# ===========================================================================


class TestCreateExperiment:
    """Test ChaosExperimentDesigner.create_experiment."""

    def test_basic_creation(self):
        eng = _engine()
        exp = eng.create_experiment(
            name="Network split test",
            experiment_type=ExperimentType.NETWORK_PARTITION,
            target_service="auth-svc",
            hypothesis="Auth service handles partition gracefully",
        )
        assert exp.id
        assert exp.name == "Network split test"
        assert exp.experiment_type == ExperimentType.NETWORK_PARTITION
        assert exp.target_service == "auth-svc"
        assert exp.hypothesis == "Auth service handles partition gracefully"
        assert exp.status == ExperimentStatus.DRAFT

    def test_eviction_on_overflow(self):
        eng = _engine(max_experiments=2)
        eng.create_experiment(name="exp-1", target_service="svc-a")
        eng.create_experiment(name="exp-2", target_service="svc-b")
        exp3 = eng.create_experiment(name="exp-3", target_service="svc-c")
        exps = eng.list_experiments(limit=10)
        assert len(exps) == 2
        assert exps[-1].id == exp3.id

    def test_with_prerequisites_and_affected(self):
        eng = _engine()
        exp = eng.create_experiment(
            name="Resource test",
            experiment_type=ExperimentType.RESOURCE_EXHAUSTION,
            target_service="api-svc",
            prerequisites=["backup-ready", "monitoring-enabled"],
            affected_services=["api-svc", "db-svc"],
        )
        assert exp.prerequisites == ["backup-ready", "monitoring-enabled"]
        assert exp.affected_services == ["api-svc", "db-svc"]


# ===========================================================================
# GetExperiment
# ===========================================================================


class TestGetExperiment:
    """Test ChaosExperimentDesigner.get_experiment."""

    def test_found(self):
        eng = _engine()
        exp = eng.create_experiment(name="test-exp", target_service="svc-a")
        assert eng.get_experiment(exp.id) is exp

    def test_not_found(self):
        eng = _engine()
        assert eng.get_experiment("nonexistent-id") is None


# ===========================================================================
# ListExperiments
# ===========================================================================


class TestListExperiments:
    """Test ChaosExperimentDesigner.list_experiments with various filters."""

    def test_all_experiments(self):
        eng = _engine()
        eng.create_experiment(name="exp-1")
        eng.create_experiment(name="exp-2")
        assert len(eng.list_experiments()) == 2

    def test_filter_by_type(self):
        eng = _engine()
        eng.create_experiment(name="net", experiment_type=ExperimentType.NETWORK_PARTITION)
        eng.create_experiment(name="kill", experiment_type=ExperimentType.SERVICE_KILL)
        results = eng.list_experiments(experiment_type=ExperimentType.SERVICE_KILL)
        assert len(results) == 1
        assert results[0].experiment_type == ExperimentType.SERVICE_KILL

    def test_filter_by_target_service(self):
        eng = _engine()
        eng.create_experiment(name="exp-1", target_service="auth-svc")
        eng.create_experiment(name="exp-2", target_service="billing-svc")
        results = eng.list_experiments(target_service="auth-svc")
        assert len(results) == 1
        assert results[0].target_service == "auth-svc"


# ===========================================================================
# EstimateBlastRadius
# ===========================================================================


class TestEstimateBlastRadius:
    """Test ChaosExperimentDesigner.estimate_blast_radius."""

    def test_minimal_no_affected(self):
        eng = _engine()
        exp = eng.create_experiment(name="solo", affected_services=[])
        result = eng.estimate_blast_radius(exp.id)
        assert result["level"] == "minimal"
        assert result["affected_count"] == 0
        assert result["exceeds_max"] is False

    def test_contained_two_services(self):
        eng = _engine()
        exp = eng.create_experiment(name="duo", affected_services=["svc-a", "svc-b"])
        result = eng.estimate_blast_radius(exp.id)
        assert result["level"] == "contained"
        assert result["affected_count"] == 2

    def test_moderate_five_services(self):
        eng = _engine()
        exp = eng.create_experiment(name="multi", affected_services=[f"svc-{i}" for i in range(5)])
        result = eng.estimate_blast_radius(exp.id)
        assert result["level"] == "moderate"

    def test_catastrophic_exceeds_max(self):
        eng = _engine(max_blast_radius=2)
        exp = eng.create_experiment(name="big", affected_services=[f"svc-{i}" for i in range(11)])
        result = eng.estimate_blast_radius(exp.id)
        assert result["level"] == "catastrophic"
        assert result["exceeds_max"] is True

    def test_not_found_returns_empty(self):
        eng = _engine()
        result = eng.estimate_blast_radius("nonexistent")
        assert result == {}


# ===========================================================================
# ValidatePrerequisites
# ===========================================================================


class TestValidatePrerequisites:
    """Test ChaosExperimentDesigner.validate_prerequisites."""

    def test_all_pass(self):
        eng = _engine()
        exp = eng.create_experiment(
            name="validated", prerequisites=["backup-ready", "alerts-silenced"]
        )
        checks = eng.validate_prerequisites(exp.id)
        assert len(checks) == 2
        assert all(c.passed for c in checks)
        assert checks[0].check_name == "backup-ready"
        assert checks[1].check_name == "alerts-silenced"

    def test_no_prerequisites(self):
        eng = _engine()
        exp = eng.create_experiment(name="no-prereqs", prerequisites=[])
        checks = eng.validate_prerequisites(exp.id)
        assert checks == []

    def test_not_found_returns_empty(self):
        eng = _engine()
        checks = eng.validate_prerequisites("nonexistent")
        assert checks == []


# ===========================================================================
# GenerateRollbackPlan
# ===========================================================================


class TestGenerateRollbackPlan:
    """Test ChaosExperimentDesigner.generate_rollback_plan."""

    def test_network_partition_steps(self):
        eng = _engine()
        exp = eng.create_experiment(
            name="net-test",
            experiment_type=ExperimentType.NETWORK_PARTITION,
            affected_services=["svc-a", "svc-b"],
        )
        plan = eng.generate_rollback_plan(exp.id)
        assert plan["experiment_id"] == exp.id
        assert len(plan["rollback_steps"]) == 3
        assert "partition" in plan["rollback_steps"][0].lower()
        assert plan["estimated_rollback_minutes"] == 10  # 5 * 2 affected

    def test_service_kill_steps(self):
        eng = _engine()
        exp = eng.create_experiment(
            name="kill-test",
            experiment_type=ExperimentType.SERVICE_KILL,
            affected_services=[],
        )
        plan = eng.generate_rollback_plan(exp.id)
        assert len(plan["rollback_steps"]) == 3
        assert plan["estimated_rollback_minutes"] == 5  # 5 * max(0,1)

    def test_not_found_returns_empty(self):
        eng = _engine()
        plan = eng.generate_rollback_plan("nonexistent")
        assert plan == {}


# ===========================================================================
# ApproveExperiment
# ===========================================================================


class TestApproveExperiment:
    """Test ChaosExperimentDesigner.approve_experiment."""

    def test_approve_draft(self):
        eng = _engine()
        exp = eng.create_experiment(name="approval-test")
        assert exp.status == ExperimentStatus.DRAFT
        approved = eng.approve_experiment(exp.id)
        assert approved is not None
        assert approved.status == ExperimentStatus.APPROVED

    def test_approve_non_draft_returns_none(self):
        eng = _engine()
        exp = eng.create_experiment(name="already-approved")
        eng.approve_experiment(exp.id)  # now APPROVED
        result = eng.approve_experiment(exp.id)  # not DRAFT anymore
        assert result is None

    def test_approve_not_found(self):
        eng = _engine()
        result = eng.approve_experiment("nonexistent")
        assert result is None


# ===========================================================================
# AnalyzeExperimentCoverage
# ===========================================================================


class TestAnalyzeExperimentCoverage:
    """Test ChaosExperimentDesigner.analyze_experiment_coverage."""

    def test_full_coverage(self):
        eng = _engine()
        for et in ExperimentType:
            eng.create_experiment(name=f"test-{et.value}", experiment_type=et)
        coverage = eng.analyze_experiment_coverage()
        assert coverage["types_covered"] == 5
        assert coverage["types_total"] == 5
        assert coverage["coverage_pct"] == 100.0
        assert coverage["uncovered_types"] == []

    def test_partial_coverage(self):
        eng = _engine()
        eng.create_experiment(name="net", experiment_type=ExperimentType.NETWORK_PARTITION)
        eng.create_experiment(name="kill", experiment_type=ExperimentType.SERVICE_KILL)
        coverage = eng.analyze_experiment_coverage()
        assert coverage["types_covered"] == 2
        assert coverage["types_total"] == 5
        assert coverage["coverage_pct"] == 40.0
        assert len(coverage["uncovered_types"]) == 3


# ===========================================================================
# GenerateDesignReport
# ===========================================================================


class TestGenerateDesignReport:
    """Test ChaosExperimentDesigner.generate_design_report."""

    def test_basic_report(self):
        eng = _engine()
        eng.create_experiment(
            name="exp-1",
            experiment_type=ExperimentType.NETWORK_PARTITION,
            blast_radius_level=BlastRadiusLevel.MINIMAL,
        )
        eng.create_experiment(
            name="exp-2",
            experiment_type=ExperimentType.SERVICE_KILL,
            blast_radius_level=BlastRadiusLevel.CONTAINED,
        )
        report = eng.generate_design_report()
        assert isinstance(report, ChaosDesignReport)
        assert report.total_experiments == 2
        assert report.by_type["network_partition"] == 1
        assert report.by_type["service_kill"] == 1
        assert report.by_status["draft"] == 2
        assert report.generated_at > 0
        assert len(report.recommendations) >= 1  # partial coverage

    def test_empty_report(self):
        eng = _engine()
        report = eng.generate_design_report()
        assert report.total_experiments == 0
        assert report.avg_blast_radius == 0.0


# ===========================================================================
# ClearData
# ===========================================================================


class TestClearData:
    """Test ChaosExperimentDesigner.clear_data."""

    def test_clears_all(self):
        eng = _engine()
        exp = eng.create_experiment(name="temp", prerequisites=["prereq-1"])
        eng.validate_prerequisites(exp.id)
        eng.clear_data()
        assert len(eng.list_experiments()) == 0
        stats = eng.get_stats()
        assert stats["total_experiments"] == 0
        assert stats["total_prerequisite_checks"] == 0


# ===========================================================================
# GetStats
# ===========================================================================


class TestGetStats:
    """Test ChaosExperimentDesigner.get_stats."""

    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_experiments"] == 0
        assert stats["total_prerequisite_checks"] == 0
        assert stats["unique_target_services"] == 0
        assert stats["type_distribution"] == {}
        assert stats["status_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.create_experiment(
            name="exp-1",
            experiment_type=ExperimentType.NETWORK_PARTITION,
            target_service="auth-svc",
        )
        eng.create_experiment(
            name="exp-2",
            experiment_type=ExperimentType.SERVICE_KILL,
            target_service="billing-svc",
        )
        stats = eng.get_stats()
        assert stats["total_experiments"] == 2
        assert stats["unique_target_services"] == 2
        assert stats["type_distribution"]["network_partition"] == 1
        assert stats["type_distribution"]["service_kill"] == 1
        assert stats["status_distribution"]["draft"] == 2
