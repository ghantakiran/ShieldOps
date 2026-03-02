"""Tests for shieldops.security.mitre_attack_mapper — MitreAttackMapper."""

from __future__ import annotations

from shieldops.security.mitre_attack_mapper import (
    AttackCoverageReport,
    AttackMapping,
    AttackTactic,
    CoverageAnalysis,
    CoverageLevel,
    MitreAttackMapper,
    TechniqueCategory,
)


def _engine(**kw) -> MitreAttackMapper:
    return MitreAttackMapper(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_tactic_initial_access(self):
        assert AttackTactic.INITIAL_ACCESS == "initial_access"

    def test_tactic_execution(self):
        assert AttackTactic.EXECUTION == "execution"

    def test_tactic_persistence(self):
        assert AttackTactic.PERSISTENCE == "persistence"

    def test_tactic_privilege_escalation(self):
        assert AttackTactic.PRIVILEGE_ESCALATION == "privilege_escalation"

    def test_tactic_defense_evasion(self):
        assert AttackTactic.DEFENSE_EVASION == "defense_evasion"

    def test_category_phishing(self):
        assert TechniqueCategory.PHISHING == "phishing"

    def test_category_exploit_public(self):
        assert TechniqueCategory.EXPLOIT_PUBLIC == "exploit_public"

    def test_category_command_scripting(self):
        assert TechniqueCategory.COMMAND_SCRIPTING == "command_scripting"

    def test_category_valid_accounts(self):
        assert TechniqueCategory.VALID_ACCOUNTS == "valid_accounts"

    def test_category_supply_chain(self):
        assert TechniqueCategory.SUPPLY_CHAIN == "supply_chain"

    def test_coverage_full(self):
        assert CoverageLevel.FULL == "full"

    def test_coverage_partial(self):
        assert CoverageLevel.PARTIAL == "partial"

    def test_coverage_minimal(self):
        assert CoverageLevel.MINIMAL == "minimal"

    def test_coverage_none(self):
        assert CoverageLevel.NONE == "none"

    def test_coverage_unknown(self):
        assert CoverageLevel.UNKNOWN == "unknown"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_attack_mapping_defaults(self):
        r = AttackMapping()
        assert r.id
        assert r.technique_id == ""
        assert r.attack_tactic == AttackTactic.INITIAL_ACCESS
        assert r.technique_category == TechniqueCategory.PHISHING
        assert r.coverage_level == CoverageLevel.FULL
        assert r.coverage_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_coverage_analysis_defaults(self):
        c = CoverageAnalysis()
        assert c.id
        assert c.technique_id == ""
        assert c.attack_tactic == AttackTactic.INITIAL_ACCESS
        assert c.analysis_score == 0.0
        assert c.threshold == 0.0
        assert c.breached is False
        assert c.description == ""
        assert c.created_at > 0

    def test_attack_coverage_report_defaults(self):
        r = AttackCoverageReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_coverage_score == 0.0
        assert r.by_tactic == {}
        assert r.by_category == {}
        assert r.by_coverage == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_mapping
# ---------------------------------------------------------------------------


class TestRecordMapping:
    def test_basic(self):
        eng = _engine()
        r = eng.record_mapping(
            technique_id="T1566",
            attack_tactic=AttackTactic.EXECUTION,
            technique_category=TechniqueCategory.EXPLOIT_PUBLIC,
            coverage_level=CoverageLevel.PARTIAL,
            coverage_score=92.0,
            service="auth-svc",
            team="security",
        )
        assert r.technique_id == "T1566"
        assert r.attack_tactic == AttackTactic.EXECUTION
        assert r.technique_category == TechniqueCategory.EXPLOIT_PUBLIC
        assert r.coverage_level == CoverageLevel.PARTIAL
        assert r.coverage_score == 92.0
        assert r.service == "auth-svc"
        assert r.team == "security"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_mapping(technique_id=f"T-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_mapping
# ---------------------------------------------------------------------------


class TestGetMapping:
    def test_found(self):
        eng = _engine()
        r = eng.record_mapping(
            technique_id="T1566",
            coverage_level=CoverageLevel.FULL,
        )
        result = eng.get_mapping(r.id)
        assert result is not None
        assert result.coverage_level == CoverageLevel.FULL

    def test_not_found(self):
        eng = _engine()
        assert eng.get_mapping("nonexistent") is None


# ---------------------------------------------------------------------------
# list_mappings
# ---------------------------------------------------------------------------


class TestListMappings:
    def test_list_all(self):
        eng = _engine()
        eng.record_mapping(technique_id="T-001")
        eng.record_mapping(technique_id="T-002")
        assert len(eng.list_mappings()) == 2

    def test_filter_by_attack_tactic(self):
        eng = _engine()
        eng.record_mapping(
            technique_id="T-001",
            attack_tactic=AttackTactic.INITIAL_ACCESS,
        )
        eng.record_mapping(
            technique_id="T-002",
            attack_tactic=AttackTactic.EXECUTION,
        )
        results = eng.list_mappings(attack_tactic=AttackTactic.INITIAL_ACCESS)
        assert len(results) == 1

    def test_filter_by_technique_category(self):
        eng = _engine()
        eng.record_mapping(
            technique_id="T-001",
            technique_category=TechniqueCategory.PHISHING,
        )
        eng.record_mapping(
            technique_id="T-002",
            technique_category=TechniqueCategory.COMMAND_SCRIPTING,
        )
        results = eng.list_mappings(
            technique_category=TechniqueCategory.PHISHING,
        )
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_mapping(technique_id="T-001", team="security")
        eng.record_mapping(technique_id="T-002", team="platform")
        results = eng.list_mappings(team="security")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_mapping(technique_id=f"T-{i}")
        assert len(eng.list_mappings(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            technique_id="T1566",
            attack_tactic=AttackTactic.EXECUTION,
            analysis_score=88.5,
            threshold=80.0,
            breached=True,
            description="coverage gap detected",
        )
        assert a.technique_id == "T1566"
        assert a.attack_tactic == AttackTactic.EXECUTION
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(technique_id=f"T-{i}")
        assert len(eng._analyses) == 2


# ---------------------------------------------------------------------------
# analyze_tactic_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeTacticDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_mapping(
            technique_id="T-001",
            attack_tactic=AttackTactic.INITIAL_ACCESS,
            coverage_score=90.0,
        )
        eng.record_mapping(
            technique_id="T-002",
            attack_tactic=AttackTactic.INITIAL_ACCESS,
            coverage_score=70.0,
        )
        result = eng.analyze_tactic_distribution()
        assert "initial_access" in result
        assert result["initial_access"]["count"] == 2
        assert result["initial_access"]["avg_coverage_score"] == 80.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_tactic_distribution() == {}


# ---------------------------------------------------------------------------
# identify_coverage_gaps
# ---------------------------------------------------------------------------


class TestIdentifyCoverageGaps:
    def test_detects_below_threshold(self):
        eng = _engine(coverage_gap_threshold=80.0)
        eng.record_mapping(technique_id="T-001", coverage_score=60.0)
        eng.record_mapping(technique_id="T-002", coverage_score=90.0)
        results = eng.identify_coverage_gaps()
        assert len(results) == 1
        assert results[0]["technique_id"] == "T-001"

    def test_sorted_ascending(self):
        eng = _engine(coverage_gap_threshold=80.0)
        eng.record_mapping(technique_id="T-001", coverage_score=50.0)
        eng.record_mapping(technique_id="T-002", coverage_score=30.0)
        results = eng.identify_coverage_gaps()
        assert len(results) == 2
        assert results[0]["coverage_score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_coverage_gaps() == []


# ---------------------------------------------------------------------------
# rank_by_coverage
# ---------------------------------------------------------------------------


class TestRankByCoverage:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_mapping(technique_id="T-001", service="auth-svc", coverage_score=90.0)
        eng.record_mapping(technique_id="T-002", service="api-gw", coverage_score=50.0)
        results = eng.rank_by_coverage()
        assert len(results) == 2
        assert results[0]["service"] == "api-gw"
        assert results[0]["avg_coverage_score"] == 50.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_coverage() == []


# ---------------------------------------------------------------------------
# detect_coverage_trends
# ---------------------------------------------------------------------------


class TestDetectCoverageTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(technique_id="T-001", analysis_score=50.0)
        result = eng.detect_coverage_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(technique_id="T-001", analysis_score=20.0)
        eng.add_analysis(technique_id="T-002", analysis_score=20.0)
        eng.add_analysis(technique_id="T-003", analysis_score=80.0)
        eng.add_analysis(technique_id="T-004", analysis_score=80.0)
        result = eng.detect_coverage_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_coverage_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(coverage_gap_threshold=80.0)
        eng.record_mapping(
            technique_id="T1566",
            attack_tactic=AttackTactic.EXECUTION,
            technique_category=TechniqueCategory.EXPLOIT_PUBLIC,
            coverage_level=CoverageLevel.PARTIAL,
            coverage_score=50.0,
        )
        report = eng.generate_report()
        assert isinstance(report, AttackCoverageReport)
        assert report.total_records == 1
        assert report.gap_count == 1
        assert len(report.top_gaps) == 1
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
        eng.record_mapping(technique_id="T-001")
        eng.add_analysis(technique_id="T-001")
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
        assert stats["tactic_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_mapping(
            technique_id="T-001",
            attack_tactic=AttackTactic.INITIAL_ACCESS,
            service="auth-svc",
            team="security",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "initial_access" in stats["tactic_distribution"]
