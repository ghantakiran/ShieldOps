"""Tests for shieldops.security.attack_chain_reconstructor — AttackChainReconstructor."""

from __future__ import annotations

from shieldops.security.attack_chain_reconstructor import (
    AttackChainReconstructor,
    AttackChainReport,
    AttackVector,
    ChainAnalysis,
    ChainConfidence,
    ChainRecord,
    KillChainPhase,
)


def _engine(**kw) -> AttackChainReconstructor:
    return AttackChainReconstructor(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_phase_reconnaissance(self):
        assert KillChainPhase.RECONNAISSANCE == "reconnaissance"

    def test_phase_weaponization(self):
        assert KillChainPhase.WEAPONIZATION == "weaponization"

    def test_phase_delivery(self):
        assert KillChainPhase.DELIVERY == "delivery"

    def test_phase_exploitation(self):
        assert KillChainPhase.EXPLOITATION == "exploitation"

    def test_phase_installation(self):
        assert KillChainPhase.INSTALLATION == "installation"

    def test_confidence_confirmed(self):
        assert ChainConfidence.CONFIRMED == "confirmed"

    def test_confidence_high(self):
        assert ChainConfidence.HIGH == "high"

    def test_confidence_medium(self):
        assert ChainConfidence.MEDIUM == "medium"

    def test_confidence_low(self):
        assert ChainConfidence.LOW == "low"

    def test_confidence_speculative(self):
        assert ChainConfidence.SPECULATIVE == "speculative"

    def test_vector_network(self):
        assert AttackVector.NETWORK == "network"

    def test_vector_email(self):
        assert AttackVector.EMAIL == "email"

    def test_vector_web(self):
        assert AttackVector.WEB == "web"

    def test_vector_physical(self):
        assert AttackVector.PHYSICAL == "physical"

    def test_vector_insider(self):
        assert AttackVector.INSIDER == "insider"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_chain_record_defaults(self):
        r = ChainRecord()
        assert r.id
        assert r.chain_name == ""
        assert r.kill_chain_phase == KillChainPhase.RECONNAISSANCE
        assert r.chain_confidence == ChainConfidence.CONFIRMED
        assert r.attack_vector == AttackVector.NETWORK
        assert r.completeness_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_chain_analysis_defaults(self):
        c = ChainAnalysis()
        assert c.id
        assert c.chain_name == ""
        assert c.kill_chain_phase == KillChainPhase.RECONNAISSANCE
        assert c.analysis_score == 0.0
        assert c.threshold == 0.0
        assert c.breached is False
        assert c.description == ""
        assert c.created_at > 0

    def test_attack_chain_report_defaults(self):
        r = AttackChainReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.incomplete_chain_count == 0
        assert r.avg_completeness_score == 0.0
        assert r.by_phase == {}
        assert r.by_confidence == {}
        assert r.by_vector == {}
        assert r.top_incomplete == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_chain
# ---------------------------------------------------------------------------


class TestRecordChain:
    def test_basic(self):
        eng = _engine()
        r = eng.record_chain(
            chain_name="apt-campaign-alpha",
            kill_chain_phase=KillChainPhase.WEAPONIZATION,
            chain_confidence=ChainConfidence.HIGH,
            attack_vector=AttackVector.EMAIL,
            completeness_score=92.0,
            service="auth-svc",
            team="security",
        )
        assert r.chain_name == "apt-campaign-alpha"
        assert r.kill_chain_phase == KillChainPhase.WEAPONIZATION
        assert r.chain_confidence == ChainConfidence.HIGH
        assert r.attack_vector == AttackVector.EMAIL
        assert r.completeness_score == 92.0
        assert r.service == "auth-svc"
        assert r.team == "security"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_chain(chain_name=f"CHAIN-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_chain
# ---------------------------------------------------------------------------


class TestGetChain:
    def test_found(self):
        eng = _engine()
        r = eng.record_chain(
            chain_name="apt-campaign-alpha",
            attack_vector=AttackVector.NETWORK,
        )
        result = eng.get_chain(r.id)
        assert result is not None
        assert result.attack_vector == AttackVector.NETWORK

    def test_not_found(self):
        eng = _engine()
        assert eng.get_chain("nonexistent") is None


# ---------------------------------------------------------------------------
# list_chains
# ---------------------------------------------------------------------------


class TestListChains:
    def test_list_all(self):
        eng = _engine()
        eng.record_chain(chain_name="CHAIN-001")
        eng.record_chain(chain_name="CHAIN-002")
        assert len(eng.list_chains()) == 2

    def test_filter_by_kill_chain_phase(self):
        eng = _engine()
        eng.record_chain(
            chain_name="CHAIN-001",
            kill_chain_phase=KillChainPhase.RECONNAISSANCE,
        )
        eng.record_chain(
            chain_name="CHAIN-002",
            kill_chain_phase=KillChainPhase.DELIVERY,
        )
        results = eng.list_chains(kill_chain_phase=KillChainPhase.RECONNAISSANCE)
        assert len(results) == 1

    def test_filter_by_chain_confidence(self):
        eng = _engine()
        eng.record_chain(
            chain_name="CHAIN-001",
            chain_confidence=ChainConfidence.CONFIRMED,
        )
        eng.record_chain(
            chain_name="CHAIN-002",
            chain_confidence=ChainConfidence.LOW,
        )
        results = eng.list_chains(
            chain_confidence=ChainConfidence.CONFIRMED,
        )
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_chain(chain_name="CHAIN-001", team="security")
        eng.record_chain(chain_name="CHAIN-002", team="platform")
        results = eng.list_chains(team="security")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_chain(chain_name=f"CHAIN-{i}")
        assert len(eng.list_chains(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            chain_name="apt-campaign-alpha",
            kill_chain_phase=KillChainPhase.WEAPONIZATION,
            analysis_score=88.5,
            threshold=80.0,
            breached=True,
            description="incomplete chain detected",
        )
        assert a.chain_name == "apt-campaign-alpha"
        assert a.kill_chain_phase == KillChainPhase.WEAPONIZATION
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(chain_name=f"CHAIN-{i}")
        assert len(eng._analyses) == 2


# ---------------------------------------------------------------------------
# analyze_phase_distribution
# ---------------------------------------------------------------------------


class TestAnalyzePhaseDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_chain(
            chain_name="CHAIN-001",
            kill_chain_phase=KillChainPhase.RECONNAISSANCE,
            completeness_score=90.0,
        )
        eng.record_chain(
            chain_name="CHAIN-002",
            kill_chain_phase=KillChainPhase.RECONNAISSANCE,
            completeness_score=70.0,
        )
        result = eng.analyze_phase_distribution()
        assert "reconnaissance" in result
        assert result["reconnaissance"]["count"] == 2
        assert result["reconnaissance"]["avg_completeness_score"] == 80.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_phase_distribution() == {}


# ---------------------------------------------------------------------------
# identify_incomplete_chains
# ---------------------------------------------------------------------------


class TestIdentifyIncompleteChains:
    def test_detects_below_threshold(self):
        eng = _engine(completeness_threshold=80.0)
        eng.record_chain(chain_name="CHAIN-001", completeness_score=60.0)
        eng.record_chain(chain_name="CHAIN-002", completeness_score=90.0)
        results = eng.identify_incomplete_chains()
        assert len(results) == 1
        assert results[0]["chain_name"] == "CHAIN-001"

    def test_sorted_ascending(self):
        eng = _engine(completeness_threshold=80.0)
        eng.record_chain(chain_name="CHAIN-001", completeness_score=50.0)
        eng.record_chain(chain_name="CHAIN-002", completeness_score=30.0)
        results = eng.identify_incomplete_chains()
        assert len(results) == 2
        assert results[0]["completeness_score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_incomplete_chains() == []


# ---------------------------------------------------------------------------
# rank_by_completeness
# ---------------------------------------------------------------------------


class TestRankByCompleteness:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_chain(chain_name="CHAIN-001", service="auth-svc", completeness_score=90.0)
        eng.record_chain(chain_name="CHAIN-002", service="api-gw", completeness_score=50.0)
        results = eng.rank_by_completeness()
        assert len(results) == 2
        assert results[0]["service"] == "api-gw"
        assert results[0]["avg_completeness_score"] == 50.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_completeness() == []


# ---------------------------------------------------------------------------
# detect_chain_trends
# ---------------------------------------------------------------------------


class TestDetectChainTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(chain_name="CHAIN-001", analysis_score=50.0)
        result = eng.detect_chain_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(chain_name="CHAIN-001", analysis_score=20.0)
        eng.add_analysis(chain_name="CHAIN-002", analysis_score=20.0)
        eng.add_analysis(chain_name="CHAIN-003", analysis_score=80.0)
        eng.add_analysis(chain_name="CHAIN-004", analysis_score=80.0)
        result = eng.detect_chain_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_chain_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(completeness_threshold=80.0)
        eng.record_chain(
            chain_name="apt-campaign-alpha",
            kill_chain_phase=KillChainPhase.WEAPONIZATION,
            chain_confidence=ChainConfidence.HIGH,
            attack_vector=AttackVector.EMAIL,
            completeness_score=50.0,
        )
        report = eng.generate_report()
        assert isinstance(report, AttackChainReport)
        assert report.total_records == 1
        assert report.incomplete_chain_count == 1
        assert len(report.top_incomplete) == 1
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
        eng.record_chain(chain_name="CHAIN-001")
        eng.add_analysis(chain_name="CHAIN-001")
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
        assert stats["phase_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_chain(
            chain_name="CHAIN-001",
            kill_chain_phase=KillChainPhase.RECONNAISSANCE,
            service="auth-svc",
            team="security",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "reconnaissance" in stats["phase_distribution"]
