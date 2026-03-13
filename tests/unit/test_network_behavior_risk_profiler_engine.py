"""Tests for NetworkBehaviorRiskProfilerEngine."""

from __future__ import annotations

from shieldops.security.network_behavior_risk_profiler_engine import (
    BehaviorCategory,
    NetworkBehaviorAnalysis,
    NetworkBehaviorRecord,
    NetworkBehaviorReport,
    NetworkBehaviorRiskProfilerEngine,
    ProfileMethod,
    ThreatLevel,
)


def _engine(**kw) -> NetworkBehaviorRiskProfilerEngine:
    return NetworkBehaviorRiskProfilerEngine(**kw)


def test_add_record():
    eng = _engine()
    r = eng.add_record(
        host_id="host-99",
        behavior_category=BehaviorCategory.BEACONING,
        profile_method=ProfileMethod.ML_BASED,
        threat_level=ThreatLevel.CRITICAL,
        risk_score=0.91,
        connection_count=300,
        bytes_transferred=10240.0,
        destination_ips=["1.2.3.4", "5.6.7.8"],
    )
    assert isinstance(r, NetworkBehaviorRecord)
    assert r.host_id == "host-99"
    assert r.connection_count == 300
    assert r.id


def test_add_record_eviction():
    eng = _engine(max_records=3)
    for i in range(5):
        eng.add_record(host_id=f"h-{i}")
    assert len(eng._records) == 3


def test_process_found():
    eng = _engine()
    r = eng.add_record(
        host_id="h-1",
        behavior_category=BehaviorCategory.BEACONING,
        threat_level=ThreatLevel.CRITICAL,
        risk_score=0.9,
        connection_count=500,
    )
    result = eng.process(r.id)
    assert isinstance(result, NetworkBehaviorAnalysis)
    assert result.host_id == "h-1"
    assert result.composite_risk > 0
    assert result.malicious_pattern is True


def test_process_not_found():
    eng = _engine()
    result = eng.process("no-match")
    assert result == {"status": "not_found", "key": "no-match"}


def test_generate_report():
    eng = _engine()
    eng.add_record(host_id="h1", threat_level=ThreatLevel.CRITICAL, risk_score=0.9)
    eng.add_record(host_id="h2", threat_level=ThreatLevel.MEDIUM, risk_score=0.5)
    eng.add_record(host_id="h3", threat_level=ThreatLevel.LOW, risk_score=0.1)
    report = eng.generate_report()
    assert isinstance(report, NetworkBehaviorReport)
    assert report.total_records == 3
    assert report.avg_risk_score > 0
    assert len(report.by_behavior_category) > 0
    assert len(report.recommendations) > 0


def test_get_stats():
    eng = _engine()
    eng.add_record(behavior_category=BehaviorCategory.SCANNING)
    eng.add_record(behavior_category=BehaviorCategory.TUNNELING)
    stats = eng.get_stats()
    assert stats["total_records"] == 2
    assert "behavior_category_distribution" in stats


def test_clear_data():
    eng = _engine()
    eng.add_record(host_id="h1")
    result = eng.clear_data()
    assert result == {"status": "cleared"}
    assert len(eng._records) == 0


def test_profile_network_behavior():
    eng = _engine()
    eng.add_record(
        host_id="h1",
        behavior_category=BehaviorCategory.BEACONING,
        threat_level=ThreatLevel.CRITICAL,
        risk_score=0.9,
        bytes_transferred=5000.0,
        destination_ips=["1.1.1.1", "2.2.2.2"],
    )
    eng.add_record(
        host_id="h1",
        behavior_category=BehaviorCategory.EXFILTRATION,
        threat_level=ThreatLevel.HIGH,
        risk_score=0.75,
        bytes_transferred=2000.0,
        destination_ips=["3.3.3.3"],
    )
    eng.add_record(
        host_id="h2",
        behavior_category=BehaviorCategory.SCANNING,
        threat_level=ThreatLevel.LOW,
        risk_score=0.2,
        bytes_transferred=100.0,
    )
    results = eng.profile_network_behavior()
    assert isinstance(results, list)
    assert len(results) == 2
    assert results[0]["host_id"] == "h1"
    assert results[0]["composite_risk"] > results[1]["composite_risk"]
    assert "unique_destinations" in results[0]


def test_detect_malicious_patterns():
    eng = _engine()
    eng.add_record(
        host_id="h1",
        behavior_category=BehaviorCategory.BEACONING,
        risk_score=0.9,
        threat_level=ThreatLevel.CRITICAL,
    )
    eng.add_record(
        host_id="h2",
        behavior_category=BehaviorCategory.SCANNING,
        risk_score=0.3,
    )
    eng.add_record(
        host_id="h3",
        behavior_category=BehaviorCategory.EXFILTRATION,
        risk_score=0.8,
        threat_level=ThreatLevel.HIGH,
    )
    results = eng.detect_malicious_patterns()
    assert isinstance(results, list)
    assert all(r["behavior_category"] in ("beaconing", "exfiltration") for r in results)
    assert results[0]["risk_score"] >= results[-1]["risk_score"]


def test_rank_hosts_by_risk():
    eng = _engine()
    eng.add_record(host_id="a", threat_level=ThreatLevel.CRITICAL, risk_score=0.9)
    eng.add_record(host_id="b", threat_level=ThreatLevel.LOW, risk_score=0.2)
    eng.add_record(host_id="c", threat_level=ThreatLevel.HIGH, risk_score=0.7)
    results = eng.rank_hosts_by_risk()
    assert isinstance(results, list)
    assert len(results) == 3
    assert results[0]["rank"] == 1
    assert results[0]["total_risk_score"] >= results[1]["total_risk_score"]
