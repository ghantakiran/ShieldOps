"""Tests for ReasoningChainIntegrityEngine."""

from __future__ import annotations

from shieldops.observability.reasoning_chain_integrity_engine import (
    EvidenceStrength,
    IntegrityStatus,
    ReasoningChainIntegrityAnalysis,
    ReasoningChainIntegrityEngine,
    ReasoningChainIntegrityRecord,
    ReasoningChainIntegrityReport,
    ViolationType,
)


def test_add_record() -> None:
    engine = ReasoningChainIntegrityEngine()
    rec = engine.add_record(
        chain_id="chain-001",
        integrity_status=IntegrityStatus.VALID,
        evidence_strength=EvidenceStrength.CONCLUSIVE,
        violation_type=ViolationType.LOGICAL_GAP,
        confidence_score=0.95,
        step_index=1,
        premise="high cpu observed",
        conclusion="resource exhaustion",
    )
    assert isinstance(rec, ReasoningChainIntegrityRecord)
    assert rec.chain_id == "chain-001"
    assert rec.confidence_score == 0.95


def test_process() -> None:
    engine = ReasoningChainIntegrityEngine()
    rec = engine.add_record(
        chain_id="chain-002",
        integrity_status=IntegrityStatus.CIRCULAR,
        evidence_strength=EvidenceStrength.CIRCUMSTANTIAL,
        confidence_score=0.5,
        step_index=3,
    )
    result = engine.process(rec.id)
    assert isinstance(result, ReasoningChainIntegrityAnalysis)
    assert result.chain_id == "chain-002"
    assert result.has_violation is True
    assert result.chain_confidence < 0.5


def test_process_not_found() -> None:
    engine = ReasoningChainIntegrityEngine()
    result = engine.process("ghost-chain")
    assert isinstance(result, dict)
    assert result["status"] == "not_found"


def test_generate_report() -> None:
    engine = ReasoningChainIntegrityEngine()
    for cid, status, ev, vt, conf in [
        ("c1", IntegrityStatus.VALID, EvidenceStrength.CONCLUSIVE, ViolationType.LOGICAL_GAP, 0.95),
        (
            "c2",
            IntegrityStatus.WEAK_LINK,
            EvidenceStrength.SUPPORTIVE,
            ViolationType.UNSUPPORTED_LEAP,
            0.6,
        ),
        (
            "c3",
            IntegrityStatus.BROKEN,
            EvidenceStrength.CIRCUMSTANTIAL,
            ViolationType.CONTRADICTION,
            0.3,
        ),
        (
            "c4",
            IntegrityStatus.CIRCULAR,
            EvidenceStrength.ABSENT,
            ViolationType.CIRCULAR_REFERENCE,
            0.1,
        ),
    ]:
        engine.add_record(
            chain_id=cid,
            integrity_status=status,
            evidence_strength=ev,
            violation_type=vt,
            confidence_score=conf,
        )
    report = engine.generate_report()
    assert isinstance(report, ReasoningChainIntegrityReport)
    assert report.total_records == 4
    assert "valid" in report.by_integrity_status
    assert len(report.invalid_chains) >= 1


def test_get_stats() -> None:
    engine = ReasoningChainIntegrityEngine()
    engine.add_record(integrity_status=IntegrityStatus.VALID, confidence_score=0.9)
    engine.add_record(integrity_status=IntegrityStatus.BROKEN, confidence_score=0.2)
    stats = engine.get_stats()
    assert stats["total_records"] == 2
    assert "integrity_status_distribution" in stats


def test_clear_data() -> None:
    engine = ReasoningChainIntegrityEngine()
    engine.add_record(chain_id="c-x")
    result = engine.clear_data()
    assert result["status"] == "cleared"
    assert engine.get_stats()["total_records"] == 0


def test_validate_chain_integrity() -> None:
    engine = ReasoningChainIntegrityEngine()
    engine.add_record(
        chain_id="valid-chain", integrity_status=IntegrityStatus.VALID, confidence_score=0.9
    )
    engine.add_record(
        chain_id="valid-chain", integrity_status=IntegrityStatus.VALID, confidence_score=0.85
    )
    engine.add_record(
        chain_id="broken-chain", integrity_status=IntegrityStatus.BROKEN, confidence_score=0.3
    )
    results = engine.validate_chain_integrity()
    assert isinstance(results, list)
    broken = next(r for r in results if r["chain_id"] == "broken-chain")
    assert broken["valid"] is False
    assert broken["violation_count"] >= 1


def test_detect_circular_reasoning() -> None:
    engine = ReasoningChainIntegrityEngine()
    engine.add_record(
        chain_id="chain-X",
        integrity_status=IntegrityStatus.CIRCULAR,
        violation_type=ViolationType.CIRCULAR_REFERENCE,
        step_index=2,
        premise="A implies B",
        conclusion="B implies A",
    )
    engine.add_record(
        chain_id="chain-Y",
        integrity_status=IntegrityStatus.VALID,
        step_index=1,
    )
    results = engine.detect_circular_reasoning()
    assert isinstance(results, list)
    assert any(r["chain_id"] == "chain-X" for r in results)
    assert all(r["violation_type"] == "circular_reference" for r in results)


def test_compute_chain_confidence() -> None:
    engine = ReasoningChainIntegrityEngine()
    engine.add_record(
        chain_id="c1",
        evidence_strength=EvidenceStrength.CONCLUSIVE,
        confidence_score=1.0,
    )
    engine.add_record(
        chain_id="c2",
        evidence_strength=EvidenceStrength.ABSENT,
        confidence_score=1.0,
    )
    results = engine.compute_chain_confidence()
    assert isinstance(results, list)
    assert results[0]["rank"] == 1
    c1 = next(r for r in results if r["chain_id"] == "c1")
    c2 = next(r for r in results if r["chain_id"] == "c2")
    assert c1["weighted_confidence"] > c2["weighted_confidence"]
