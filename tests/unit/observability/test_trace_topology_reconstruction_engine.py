"""Tests for TraceTopologyReconstructionEngine."""

from __future__ import annotations

from shieldops.observability.trace_topology_reconstruction_engine import (
    ChangeType,
    ReconstructionAccuracy,
    TopologyType,
    TraceTopologyAnalysis,
    TraceTopologyReconstructionEngine,
    TraceTopologyRecord,
    TraceTopologyReport,
)


def test_add_record() -> None:
    engine = TraceTopologyReconstructionEngine()
    rec = engine.add_record(
        trace_id="t1",
        source_service="svc-a",
        target_service="svc-b",
        topology_type=TopologyType.DYNAMIC,
        reconstruction_accuracy=ReconstructionAccuracy.EXACT,
        change_type=ChangeType.WEIGHT_CHANGE,
        edge_weight=0.8,
        call_count=500,
        error_count=5,
    )
    assert isinstance(rec, TraceTopologyRecord)
    assert rec.source_service == "svc-a"
    assert rec.call_count == 500


def test_process() -> None:
    engine = TraceTopologyReconstructionEngine()
    rec = engine.add_record(
        source_service="svc-x",
        target_service="svc-y",
        reconstruction_accuracy=ReconstructionAccuracy.EXACT,
        change_type=ChangeType.NEW_EDGE,
    )
    result = engine.process(rec.id)
    assert isinstance(result, TraceTopologyAnalysis)
    assert result.source_service == "svc-x"
    assert result.accuracy_score == 100.0
    assert result.change_detected is True


def test_process_not_found() -> None:
    engine = TraceTopologyReconstructionEngine()
    result = engine.process("ghost-id")
    assert isinstance(result, dict)
    assert result["status"] == "not_found"


def test_generate_report() -> None:
    engine = TraceTopologyReconstructionEngine()
    for src, tgt, ttype, acc, ctype in [
        ("a", "b", TopologyType.DYNAMIC, ReconstructionAccuracy.EXACT, ChangeType.NEW_EDGE),
        (
            "b",
            "c",
            TopologyType.STATIC,
            ReconstructionAccuracy.APPROXIMATE,
            ChangeType.REMOVED_EDGE,
        ),
        ("c", "d", TopologyType.HYBRID, ReconstructionAccuracy.PARTIAL, ChangeType.WEIGHT_CHANGE),
        ("d", "e", TopologyType.INFERRED, ReconstructionAccuracy.OUTDATED, ChangeType.NODE_CHANGE),
    ]:
        engine.add_record(
            source_service=src,
            target_service=tgt,
            topology_type=ttype,
            reconstruction_accuracy=acc,
            change_type=ctype,
        )
    report = engine.generate_report()
    assert isinstance(report, TraceTopologyReport)
    assert report.total_records == 4
    assert "dynamic" in report.by_topology_type


def test_get_stats() -> None:
    engine = TraceTopologyReconstructionEngine()
    engine.add_record(topology_type=TopologyType.DYNAMIC, source_service="a", target_service="b")
    engine.add_record(topology_type=TopologyType.STATIC, source_service="c", target_service="d")
    stats = engine.get_stats()
    assert stats["total_records"] == 2
    assert "topology_type_distribution" in stats


def test_clear_data() -> None:
    engine = TraceTopologyReconstructionEngine()
    engine.add_record(source_service="x", target_service="y")
    result = engine.clear_data()
    assert result["status"] == "cleared"
    assert engine.get_stats()["total_records"] == 0


def test_reconstruct_service_topology() -> None:
    engine = TraceTopologyReconstructionEngine()
    engine.add_record(
        source_service="svc-a",
        target_service="svc-b",
        call_count=100,
        error_count=5,
        edge_weight=0.9,
    )
    engine.add_record(
        source_service="svc-b",
        target_service="svc-c",
        call_count=80,
        error_count=2,
        edge_weight=0.8,
    )
    engine.add_record(
        source_service="svc-a",
        target_service="svc-b",
        call_count=50,
        error_count=1,
        edge_weight=0.7,
    )
    results = engine.reconstruct_service_topology()
    assert isinstance(results, list)
    assert len(results) >= 1
    assert "source_service" in results[0]
    assert "error_rate_pct" in results[0]


def test_detect_topology_changes() -> None:
    engine = TraceTopologyReconstructionEngine()
    engine.add_record(
        source_service="a", target_service="b", change_type=ChangeType.NEW_EDGE, trace_id="t1"
    )
    engine.add_record(
        source_service="b", target_service="c", change_type=ChangeType.REMOVED_EDGE, trace_id="t2"
    )
    engine.add_record(
        source_service="a", target_service="b", change_type=ChangeType.NEW_EDGE, trace_id="t3"
    )
    results = engine.detect_topology_changes()
    assert isinstance(results, list)
    assert len(results) >= 1
    assert "change_count" in results[0]
    assert results[0]["change_count"] >= 1


def test_validate_topology_accuracy() -> None:
    engine = TraceTopologyReconstructionEngine()
    engine.add_record(
        source_service="a", target_service="b", reconstruction_accuracy=ReconstructionAccuracy.EXACT
    )
    engine.add_record(
        source_service="b",
        target_service="c",
        reconstruction_accuracy=ReconstructionAccuracy.OUTDATED,
    )
    engine.add_record(
        source_service="a",
        target_service="b",
        reconstruction_accuracy=ReconstructionAccuracy.APPROXIMATE,
    )
    results = engine.validate_topology_accuracy()
    assert isinstance(results, list)
    assert len(results) >= 1
    assert "avg_accuracy_pct" in results[0]
    assert "accuracy_ok" in results[0]
