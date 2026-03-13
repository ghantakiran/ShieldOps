"""Tests for RecoveryDependencyMapper."""

import pytest

from shieldops.operations.recovery_dependency_mapper import (
    DependencyRisk,
    DependencyType,
    RecoveryDependencyAnalysis,
    RecoveryDependencyMapper,
    RecoveryDependencyRecord,
    RecoveryDependencyReport,
    RecoveryOrder,
)


@pytest.fixture
def engine():
    return RecoveryDependencyMapper(max_records=1000)


def test_engine_init(engine):
    assert engine._max_records == 1000
    assert engine._records == []
    assert engine._analyses == {}


def test_record_item_defaults(engine):
    rec = engine.record_item()
    assert isinstance(rec, RecoveryDependencyRecord)
    assert rec.dependency_type == DependencyType.HARD


def test_record_item_custom(engine):
    rec = engine.record_item(
        name="api-to-db",
        source_service="api",
        target_service="db",
        dependency_type=DependencyType.HARD,
        recovery_order=RecoveryOrder.SEQUENTIAL,
        dependency_risk=DependencyRisk.CRITICAL,
        recovery_time_seconds=120,
        score=0.9,
    )
    assert rec.source_service == "api"
    assert rec.target_service == "db"


def test_record_item_ring_buffer():
    engine = RecoveryDependencyMapper(max_records=3)
    for i in range(5):
        engine.record_item(name=f"dep-{i}")
    assert len(engine._records) == 3


def test_process_found(engine):
    rec = engine.record_item(source_service="api", target_service="db")
    result = engine.process(rec.id)
    assert isinstance(result, RecoveryDependencyAnalysis)
    assert result.source_service == "api"


def test_process_circular(engine):
    engine.record_item(source_service="api", target_service="api")
    rec = engine.record_item(source_service="api", target_service="db")
    result = engine.process(rec.id)
    assert result.has_circular is True


def test_process_not_found(engine):
    result = engine.process("nonexistent")
    assert result["status"] == "not_found"


def test_generate_report_empty(engine):
    report = engine.generate_report()
    assert isinstance(report, RecoveryDependencyReport)
    assert report.total_records == 0


def test_generate_report_with_data(engine):
    engine.record_item(dependency_type=DependencyType.HARD, score=80)
    engine.record_item(dependency_type=DependencyType.SOFT, score=40)
    report = engine.generate_report()
    assert report.total_records == 2
    assert report.avg_score == 60.0


def test_get_stats(engine):
    engine.record_item(dependency_type=DependencyType.OPTIONAL)
    stats = engine.get_stats()
    assert stats["total_records"] == 1
    assert "optional" in stats["dependency_type_distribution"]


def test_clear_data(engine):
    engine.record_item()
    result = engine.clear_data()
    assert result == {"status": "cleared"}
    assert engine._records == []


def test_compute_recovery_critical_path(engine):
    engine.record_item(
        source_service="api",
        target_service="db",
        dependency_type=DependencyType.HARD,
        recovery_time_seconds=60,
    )
    engine.record_item(
        source_service="api",
        target_service="cache",
        dependency_type=DependencyType.HARD,
        recovery_time_seconds=30,
    )
    engine.record_item(
        source_service="web",
        target_service="api",
        dependency_type=DependencyType.SOFT,
        recovery_time_seconds=45,
    )
    result = engine.compute_recovery_critical_path()
    assert len(result) == 2
    assert result[0]["critical_path_time"] >= result[1]["critical_path_time"]


def test_compute_recovery_critical_path_empty(engine):
    assert engine.compute_recovery_critical_path() == []


def test_detect_circular_dependencies(engine):
    engine.record_item(source_service="api", target_service="db")
    engine.record_item(source_service="db", target_service="api")
    result = engine.detect_circular_dependencies()
    assert len(result) == 1
    assert result[0]["circular"] is True


def test_detect_circular_dependencies_empty(engine):
    assert engine.detect_circular_dependencies() == []


def test_rank_services_by_recovery_priority(engine):
    engine.record_item(source_service="api", dependency_type=DependencyType.HARD, score=90)
    engine.record_item(source_service="web", dependency_type=DependencyType.SOFT, score=40)
    result = engine.rank_services_by_recovery_priority()
    assert len(result) == 2
    assert result[0]["rank"] == 1


def test_rank_services_by_recovery_priority_empty(engine):
    assert engine.rank_services_by_recovery_priority() == []


def test_enum_values():
    assert DependencyType.CONDITIONAL == "conditional"
    assert RecoveryOrder.STAGED == "staged"
    assert DependencyRisk.LOW == "low"
