"""Tests for shieldops.security.honeypot_interaction_analyzer — HoneypotInteractionAnalyzer."""

from __future__ import annotations

from shieldops.security.honeypot_interaction_analyzer import (
    AttackerSophistication,
    HoneypotInteractionAnalyzer,
    InteractionAnalysis,
    InteractionRecord,
    InteractionReport,
    InteractionType,
    TTPClassification,
)


def _engine(**kw) -> HoneypotInteractionAnalyzer:
    return HoneypotInteractionAnalyzer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_type_port_scan(self):
        assert InteractionType.PORT_SCAN == "port_scan"

    def test_type_login_attempt(self):
        assert InteractionType.LOGIN_ATTEMPT == "login_attempt"

    def test_type_file_access(self):
        assert InteractionType.FILE_ACCESS == "file_access"

    def test_type_command_execution(self):
        assert InteractionType.COMMAND_EXECUTION == "command_execution"

    def test_type_data_exfiltration(self):
        assert InteractionType.DATA_EXFILTRATION == "data_exfiltration"

    def test_sophistication_nation_state(self):
        assert AttackerSophistication.NATION_STATE == "nation_state"

    def test_sophistication_advanced(self):
        assert AttackerSophistication.ADVANCED == "advanced"

    def test_sophistication_intermediate(self):
        assert AttackerSophistication.INTERMEDIATE == "intermediate"

    def test_sophistication_script_kiddie(self):
        assert AttackerSophistication.SCRIPT_KIDDIE == "script_kiddie"

    def test_sophistication_automated(self):
        assert AttackerSophistication.AUTOMATED == "automated"

    def test_ttp_reconnaissance(self):
        assert TTPClassification.RECONNAISSANCE == "reconnaissance"

    def test_ttp_initial_access(self):
        assert TTPClassification.INITIAL_ACCESS == "initial_access"

    def test_ttp_execution(self):
        assert TTPClassification.EXECUTION == "execution"

    def test_ttp_persistence(self):
        assert TTPClassification.PERSISTENCE == "persistence"

    def test_ttp_collection(self):
        assert TTPClassification.COLLECTION == "collection"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_interaction_record_defaults(self):
        r = InteractionRecord()
        assert r.id
        assert r.interaction_name == ""
        assert r.interaction_type == InteractionType.PORT_SCAN
        assert r.attacker_sophistication == AttackerSophistication.NATION_STATE
        assert r.ttp_classification == TTPClassification.RECONNAISSANCE
        assert r.threat_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_interaction_analysis_defaults(self):
        a = InteractionAnalysis()
        assert a.id
        assert a.interaction_name == ""
        assert a.interaction_type == InteractionType.PORT_SCAN
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_interaction_report_defaults(self):
        r = InteractionReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.high_threat_count == 0
        assert r.avg_threat_score == 0.0
        assert r.by_type == {}
        assert r.by_sophistication == {}
        assert r.by_ttp == {}
        assert r.top_high_threat == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_interaction
# ---------------------------------------------------------------------------


class TestRecordInteraction:
    def test_basic(self):
        eng = _engine()
        r = eng.record_interaction(
            interaction_name="ssh-brute-force",
            interaction_type=InteractionType.LOGIN_ATTEMPT,
            attacker_sophistication=AttackerSophistication.ADVANCED,
            ttp_classification=TTPClassification.INITIAL_ACCESS,
            threat_score=85.0,
            service="honeypot-svc",
            team="security",
        )
        assert r.interaction_name == "ssh-brute-force"
        assert r.interaction_type == InteractionType.LOGIN_ATTEMPT
        assert r.attacker_sophistication == AttackerSophistication.ADVANCED
        assert r.ttp_classification == TTPClassification.INITIAL_ACCESS
        assert r.threat_score == 85.0
        assert r.service == "honeypot-svc"
        assert r.team == "security"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_interaction(interaction_name=f"INT-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_interaction
# ---------------------------------------------------------------------------


class TestGetInteraction:
    def test_found(self):
        eng = _engine()
        r = eng.record_interaction(
            interaction_name="ssh-brute-force",
            interaction_type=InteractionType.LOGIN_ATTEMPT,
        )
        result = eng.get_interaction(r.id)
        assert result is not None
        assert result.interaction_type == InteractionType.LOGIN_ATTEMPT

    def test_not_found(self):
        eng = _engine()
        assert eng.get_interaction("nonexistent") is None


# ---------------------------------------------------------------------------
# list_interactions
# ---------------------------------------------------------------------------


class TestListInteractions:
    def test_list_all(self):
        eng = _engine()
        eng.record_interaction(interaction_name="INT-001")
        eng.record_interaction(interaction_name="INT-002")
        assert len(eng.list_interactions()) == 2

    def test_filter_by_type(self):
        eng = _engine()
        eng.record_interaction(
            interaction_name="INT-001",
            interaction_type=InteractionType.PORT_SCAN,
        )
        eng.record_interaction(
            interaction_name="INT-002",
            interaction_type=InteractionType.LOGIN_ATTEMPT,
        )
        results = eng.list_interactions(interaction_type=InteractionType.PORT_SCAN)
        assert len(results) == 1

    def test_filter_by_sophistication(self):
        eng = _engine()
        eng.record_interaction(
            interaction_name="INT-001",
            attacker_sophistication=AttackerSophistication.NATION_STATE,
        )
        eng.record_interaction(
            interaction_name="INT-002",
            attacker_sophistication=AttackerSophistication.SCRIPT_KIDDIE,
        )
        results = eng.list_interactions(
            attacker_sophistication=AttackerSophistication.NATION_STATE,
        )
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_interaction(interaction_name="INT-001", team="security")
        eng.record_interaction(interaction_name="INT-002", team="platform")
        results = eng.list_interactions(team="security")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_interaction(interaction_name=f"INT-{i}")
        assert len(eng.list_interactions(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            interaction_name="ssh-brute-force",
            interaction_type=InteractionType.COMMAND_EXECUTION,
            analysis_score=88.5,
            threshold=60.0,
            breached=True,
            description="TTP extraction from honeypot",
        )
        assert a.interaction_name == "ssh-brute-force"
        assert a.interaction_type == InteractionType.COMMAND_EXECUTION
        assert a.analysis_score == 88.5
        assert a.threshold == 60.0
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(interaction_name=f"INT-{i}")
        assert len(eng._analyses) == 2


# ---------------------------------------------------------------------------
# analyze_interaction_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeInteractionDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_interaction(
            interaction_name="INT-001",
            interaction_type=InteractionType.PORT_SCAN,
            threat_score=90.0,
        )
        eng.record_interaction(
            interaction_name="INT-002",
            interaction_type=InteractionType.PORT_SCAN,
            threat_score=70.0,
        )
        result = eng.analyze_interaction_distribution()
        assert "port_scan" in result
        assert result["port_scan"]["count"] == 2
        assert result["port_scan"]["avg_threat_score"] == 80.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_interaction_distribution() == {}


# ---------------------------------------------------------------------------
# identify_high_threat_interactions
# ---------------------------------------------------------------------------


class TestIdentifyHighThreatInteractions:
    def test_detects_above_threshold(self):
        eng = _engine(threat_score_threshold=60.0)
        eng.record_interaction(interaction_name="INT-001", threat_score=80.0)
        eng.record_interaction(interaction_name="INT-002", threat_score=40.0)
        results = eng.identify_high_threat_interactions()
        assert len(results) == 1
        assert results[0]["interaction_name"] == "INT-001"

    def test_sorted_descending(self):
        eng = _engine(threat_score_threshold=60.0)
        eng.record_interaction(interaction_name="INT-001", threat_score=70.0)
        eng.record_interaction(interaction_name="INT-002", threat_score=90.0)
        results = eng.identify_high_threat_interactions()
        assert len(results) == 2
        assert results[0]["threat_score"] == 90.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_high_threat_interactions() == []


# ---------------------------------------------------------------------------
# rank_by_threat
# ---------------------------------------------------------------------------


class TestRankByThreat:
    def test_sorted_descending(self):
        eng = _engine()
        eng.record_interaction(
            interaction_name="INT-001", service="honeypot-svc", threat_score=90.0
        )
        eng.record_interaction(interaction_name="INT-002", service="decoy-svc", threat_score=50.0)
        results = eng.rank_by_threat()
        assert len(results) == 2
        assert results[0]["service"] == "honeypot-svc"
        assert results[0]["avg_threat_score"] == 90.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_threat() == []


# ---------------------------------------------------------------------------
# detect_interaction_trends
# ---------------------------------------------------------------------------


class TestDetectInteractionTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(interaction_name="INT-001", analysis_score=50.0)
        result = eng.detect_interaction_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(interaction_name="INT-001", analysis_score=20.0)
        eng.add_analysis(interaction_name="INT-002", analysis_score=20.0)
        eng.add_analysis(interaction_name="INT-003", analysis_score=80.0)
        eng.add_analysis(interaction_name="INT-004", analysis_score=80.0)
        result = eng.detect_interaction_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_interaction_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(threat_score_threshold=60.0)
        eng.record_interaction(
            interaction_name="ssh-brute-force",
            interaction_type=InteractionType.LOGIN_ATTEMPT,
            attacker_sophistication=AttackerSophistication.ADVANCED,
            ttp_classification=TTPClassification.INITIAL_ACCESS,
            threat_score=80.0,
        )
        report = eng.generate_report()
        assert isinstance(report, InteractionReport)
        assert report.total_records == 1
        assert report.high_threat_count == 1
        assert len(report.top_high_threat) == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "healthy" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_interaction(interaction_name="INT-001")
        eng.add_analysis(interaction_name="INT-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_analyses"] == 0
        assert stats["type_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_interaction(
            interaction_name="INT-001",
            interaction_type=InteractionType.PORT_SCAN,
            service="honeypot-svc",
            team="security",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "port_scan" in stats["type_distribution"]
