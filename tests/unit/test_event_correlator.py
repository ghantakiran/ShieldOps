"""Tests for shieldops.security.event_correlator — SecurityEventCorrelator."""

from __future__ import annotations

from shieldops.security.event_correlator import (
    ChainStage,
    EventChain,
    EventRecord,
    EventSource,
    SecurityEventCorrelator,
    SecurityEventReport,
    ThreatLevel,
)


def _engine(**kw) -> SecurityEventCorrelator:
    return SecurityEventCorrelator(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_source_firewall(self):
        assert EventSource.FIREWALL == "firewall"

    def test_source_ids(self):
        assert EventSource.IDS == "ids"

    def test_source_endpoint(self):
        assert EventSource.ENDPOINT == "endpoint"

    def test_source_cloud_trail(self):
        assert EventSource.CLOUD_TRAIL == "cloud_trail"

    def test_source_application(self):
        assert EventSource.APPLICATION == "application"

    def test_stage_reconnaissance(self):
        assert ChainStage.RECONNAISSANCE == "reconnaissance"

    def test_stage_initial_access(self):
        assert ChainStage.INITIAL_ACCESS == "initial_access"

    def test_stage_lateral_movement(self):
        assert ChainStage.LATERAL_MOVEMENT == "lateral_movement"

    def test_stage_exfiltration(self):
        assert ChainStage.EXFILTRATION == "exfiltration"

    def test_stage_persistence(self):
        assert ChainStage.PERSISTENCE == "persistence"

    def test_threat_critical(self):
        assert ThreatLevel.CRITICAL == "critical"

    def test_threat_high(self):
        assert ThreatLevel.HIGH == "high"

    def test_threat_moderate(self):
        assert ThreatLevel.MODERATE == "moderate"

    def test_threat_low(self):
        assert ThreatLevel.LOW == "low"

    def test_threat_benign(self):
        assert ThreatLevel.BENIGN == "benign"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_event_record_defaults(self):
        r = EventRecord()
        assert r.id
        assert r.event_id == ""
        assert r.source == EventSource.FIREWALL
        assert r.chain_stage == ChainStage.RECONNAISSANCE
        assert r.threat_level == ThreatLevel.BENIGN
        assert r.confidence_score == 0.0
        assert r.team == ""
        assert r.details == ""
        assert r.created_at > 0

    def test_event_chain_defaults(self):
        c = EventChain()
        assert c.id
        assert c.chain_name == ""
        assert c.source == EventSource.FIREWALL
        assert c.chain_stage == ChainStage.RECONNAISSANCE
        assert c.event_count == 0
        assert c.avg_threat_score == 0.0
        assert c.created_at > 0

    def test_security_event_report_defaults(self):
        r = SecurityEventReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_chains == 0
        assert r.active_chains == 0
        assert r.critical_events == 0
        assert r.by_source == {}
        assert r.by_stage == {}
        assert r.by_threat == {}
        assert r.attack_chain_alerts == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_event
# ---------------------------------------------------------------------------


class TestRecordEvent:
    def test_basic(self):
        eng = _engine()
        r = eng.record_event(
            event_id="EVT-001",
            source=EventSource.IDS,
            chain_stage=ChainStage.INITIAL_ACCESS,
            threat_level=ThreatLevel.HIGH,
            confidence_score=85.0,
            team="sre",
        )
        assert r.event_id == "EVT-001"
        assert r.source == EventSource.IDS
        assert r.chain_stage == ChainStage.INITIAL_ACCESS
        assert r.threat_level == ThreatLevel.HIGH
        assert r.confidence_score == 85.0
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_event(event_id=f"EVT-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_event
# ---------------------------------------------------------------------------


class TestGetEvent:
    def test_found(self):
        eng = _engine()
        r = eng.record_event(
            event_id="EVT-001",
            threat_level=ThreatLevel.HIGH,
        )
        result = eng.get_event(r.id)
        assert result is not None
        assert result.threat_level == ThreatLevel.HIGH

    def test_not_found(self):
        eng = _engine()
        assert eng.get_event("nonexistent") is None


# ---------------------------------------------------------------------------
# list_events
# ---------------------------------------------------------------------------


class TestListEvents:
    def test_list_all(self):
        eng = _engine()
        eng.record_event(event_id="EVT-001")
        eng.record_event(event_id="EVT-002")
        assert len(eng.list_events()) == 2

    def test_filter_by_source(self):
        eng = _engine()
        eng.record_event(
            event_id="EVT-001",
            source=EventSource.FIREWALL,
        )
        eng.record_event(
            event_id="EVT-002",
            source=EventSource.ENDPOINT,
        )
        results = eng.list_events(source=EventSource.FIREWALL)
        assert len(results) == 1

    def test_filter_by_chain_stage(self):
        eng = _engine()
        eng.record_event(
            event_id="EVT-001",
            chain_stage=ChainStage.RECONNAISSANCE,
        )
        eng.record_event(
            event_id="EVT-002",
            chain_stage=ChainStage.EXFILTRATION,
        )
        results = eng.list_events(chain_stage=ChainStage.RECONNAISSANCE)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_event(event_id="EVT-001", team="sre")
        eng.record_event(event_id="EVT-002", team="platform")
        results = eng.list_events(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_event(event_id=f"EVT-{i}")
        assert len(eng.list_events(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_chain
# ---------------------------------------------------------------------------


class TestAddChain:
    def test_basic(self):
        eng = _engine()
        c = eng.add_chain(
            chain_name="brute-force-chain",
            source=EventSource.IDS,
            chain_stage=ChainStage.LATERAL_MOVEMENT,
            event_count=12,
            avg_threat_score=78.5,
        )
        assert c.chain_name == "brute-force-chain"
        assert c.source == EventSource.IDS
        assert c.chain_stage == ChainStage.LATERAL_MOVEMENT
        assert c.event_count == 12
        assert c.avg_threat_score == 78.5

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_chain(chain_name=f"chain-{i}")
        assert len(eng._chains) == 2


# ---------------------------------------------------------------------------
# analyze_event_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeEventDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_event(
            event_id="EVT-001",
            source=EventSource.FIREWALL,
            confidence_score=80.0,
        )
        eng.record_event(
            event_id="EVT-002",
            source=EventSource.FIREWALL,
            confidence_score=60.0,
        )
        result = eng.analyze_event_distribution()
        assert "firewall" in result
        assert result["firewall"]["count"] == 2
        assert result["firewall"]["avg_confidence"] == 70.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_event_distribution() == {}


# ---------------------------------------------------------------------------
# identify_critical_events
# ---------------------------------------------------------------------------


class TestIdentifyCriticalEvents:
    def test_detects_critical(self):
        eng = _engine()
        eng.record_event(
            event_id="EVT-001",
            threat_level=ThreatLevel.CRITICAL,
            confidence_score=90.0,
        )
        eng.record_event(
            event_id="EVT-002",
            threat_level=ThreatLevel.LOW,
        )
        results = eng.identify_critical_events()
        assert len(results) == 1
        assert results[0]["event_id"] == "EVT-001"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_critical_events() == []


# ---------------------------------------------------------------------------
# rank_by_threat_score
# ---------------------------------------------------------------------------


class TestRankByThreatScore:
    def test_ranked_descending(self):
        eng = _engine()
        eng.record_event(event_id="EVT-001", team="sre", confidence_score=90.0)
        eng.record_event(event_id="EVT-002", team="sre", confidence_score=80.0)
        eng.record_event(
            event_id="EVT-003",
            team="platform",
            confidence_score=50.0,
        )
        results = eng.rank_by_threat_score()
        assert len(results) == 2
        assert results[0]["team"] == "sre"
        assert results[0]["avg_confidence"] == 85.0
        assert results[0]["event_count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_threat_score() == []


# ---------------------------------------------------------------------------
# detect_event_trends
# ---------------------------------------------------------------------------


class TestDetectEventTrends:
    def test_stable(self):
        eng = _engine()
        for score in [50.0, 50.0, 50.0, 50.0]:
            eng.record_event(event_id="EVT", confidence_score=score)
        result = eng.detect_event_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        for score in [10.0, 10.0, 30.0, 30.0]:
            eng.record_event(event_id="EVT", confidence_score=score)
        result = eng.detect_event_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_event_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_event(
            event_id="EVT-001",
            source=EventSource.FIREWALL,
            threat_level=ThreatLevel.CRITICAL,
            confidence_score=90.0,
            team="sre",
        )
        report = eng.generate_report()
        assert isinstance(report, SecurityEventReport)
        assert report.total_records == 1
        assert report.critical_events == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "healthy" in report.recommendations[0]

    def test_low_confidence_recommendation(self):
        eng = _engine(min_threat_confidence_pct=80.0)
        eng.record_event(
            event_id="EVT-001",
            confidence_score=50.0,
        )
        report = eng.generate_report()
        assert any("below confidence" in r for r in report.recommendations)


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_event(event_id="EVT-001")
        eng.add_chain(chain_name="c1")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._chains) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_chains"] == 0
        assert stats["source_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_event(
            event_id="EVT-001",
            source=EventSource.IDS,
            team="sre",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_events"] == 1
        assert "ids" in stats["source_distribution"]
