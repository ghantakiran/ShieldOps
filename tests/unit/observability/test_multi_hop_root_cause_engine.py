"""Tests for MultiHopRootCauseEngine."""

from __future__ import annotations

from shieldops.observability.multi_hop_root_cause_engine import (
    CausalLinkType,
    ChainStatus,
    HopDepth,
    MultiHopRootCauseAnalysis,
    MultiHopRootCauseEngine,
    MultiHopRootCauseRecord,
    MultiHopRootCauseReport,
)


def test_add_record() -> None:
    engine = MultiHopRootCauseEngine()
    rec = engine.add_record(
        chain_id="chain-1",
        hop_depth=HopDepth.TWO_HOP,
        causal_link_type=CausalLinkType.DIRECT,
        chain_status=ChainStatus.COMPLETE,
        confidence_score=0.9,
        hop_count=2,
        root_cause="db-timeout",
    )
    assert isinstance(rec, MultiHopRootCauseRecord)
    assert rec.chain_id == "chain-1"
    assert rec.hop_count == 2


def test_process() -> None:
    engine = MultiHopRootCauseEngine()
    rec = engine.add_record(
        chain_id="chain-2",
        hop_depth=HopDepth.THREE_HOP,
        chain_status=ChainStatus.COMPLETE,
        confidence_score=0.85,
        hop_count=3,
    )
    result = engine.process(rec.id)
    assert isinstance(result, MultiHopRootCauseAnalysis)
    assert result.chain_id == "chain-2"
    assert result.dependency_valid is True
    assert result.confidence_score == 0.85


def test_process_not_found() -> None:
    engine = MultiHopRootCauseEngine()
    result = engine.process("nonexistent-id")
    assert isinstance(result, dict)
    assert result["status"] == "not_found"


def test_generate_report() -> None:
    engine = MultiHopRootCauseEngine()
    for cid, depth, link, status, conf in [
        ("c1", HopDepth.SINGLE_HOP, CausalLinkType.DIRECT, ChainStatus.COMPLETE, 0.95),
        ("c2", HopDepth.TWO_HOP, CausalLinkType.INDIRECT, ChainStatus.PARTIAL, 0.7),
        ("c3", HopDepth.THREE_HOP, CausalLinkType.SPECULATIVE, ChainStatus.BROKEN, 0.4),
        ("c4", HopDepth.DEEP_HOP, CausalLinkType.CORRELATED, ChainStatus.UNVERIFIED, 0.5),
    ]:
        engine.add_record(
            chain_id=cid,
            hop_depth=depth,
            causal_link_type=link,
            chain_status=status,
            confidence_score=conf,
        )
    report = engine.generate_report()
    assert isinstance(report, MultiHopRootCauseReport)
    assert report.total_records == 4
    assert "single_hop" in report.by_hop_depth


def test_get_stats() -> None:
    engine = MultiHopRootCauseEngine()
    engine.add_record(hop_depth=HopDepth.SINGLE_HOP, confidence_score=0.9)
    engine.add_record(hop_depth=HopDepth.TWO_HOP, confidence_score=0.8)
    stats = engine.get_stats()
    assert stats["total_records"] == 2
    assert "hop_depth_distribution" in stats


def test_clear_data() -> None:
    engine = MultiHopRootCauseEngine()
    engine.add_record(chain_id="c-x")
    result = engine.clear_data()
    assert result["status"] == "cleared"
    assert engine.get_stats()["total_records"] == 0


def test_trace_causal_chain() -> None:
    engine = MultiHopRootCauseEngine()
    engine.add_record(chain_id="chain-A", hop_count=1, confidence_score=0.9)
    engine.add_record(chain_id="chain-A", hop_count=2, confidence_score=0.8)
    engine.add_record(chain_id="chain-B", hop_count=3, confidence_score=0.6)
    results = engine.trace_causal_chain()
    assert isinstance(results, list)
    assert len(results) >= 1
    assert "chain_id" in results[0]
    assert results[0]["avg_confidence"] >= results[-1]["avg_confidence"]


def test_validate_hop_dependencies() -> None:
    engine = MultiHopRootCauseEngine()
    engine.add_record(
        chain_id="chain-X",
        chain_status=ChainStatus.COMPLETE,
        causal_link_type=CausalLinkType.DIRECT,
    )
    engine.add_record(
        chain_id="chain-Y",
        chain_status=ChainStatus.BROKEN,
        causal_link_type=CausalLinkType.SPECULATIVE,
    )
    results = engine.validate_hop_dependencies()
    assert isinstance(results, list)
    y_result = next(r for r in results if r["chain_id"] == "chain-Y")
    assert y_result["broken_hops"] >= 1
    assert y_result["valid"] is False


def test_rank_chains_by_confidence() -> None:
    engine = MultiHopRootCauseEngine()
    engine.add_record(chain_id="c1", confidence_score=0.95, hop_depth=HopDepth.SINGLE_HOP)
    engine.add_record(chain_id="c2", confidence_score=0.5, hop_depth=HopDepth.TWO_HOP)
    engine.add_record(chain_id="c3", confidence_score=0.75, hop_depth=HopDepth.THREE_HOP)
    results = engine.rank_chains_by_confidence()
    assert isinstance(results, list)
    assert results[0]["rank"] == 1
    assert results[0]["avg_confidence"] >= results[-1]["avg_confidence"]
