"""Tests for shieldops.operations.team_skill_matrix — TeamSkillMatrix."""

from __future__ import annotations

from shieldops.operations.team_skill_matrix import (
    GapSeverity,
    SkillDomain,
    SkillEntry,
    SkillGap,
    SkillLevel,
    SkillMatrixReport,
    TeamSkillMatrix,
)


def _engine(**kw) -> TeamSkillMatrix:
    return TeamSkillMatrix(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    # SkillLevel (5)
    def test_level_novice(self):
        assert SkillLevel.NOVICE == "novice"

    def test_level_beginner(self):
        assert SkillLevel.BEGINNER == "beginner"

    def test_level_intermediate(self):
        assert SkillLevel.INTERMEDIATE == "intermediate"

    def test_level_advanced(self):
        assert SkillLevel.ADVANCED == "advanced"

    def test_level_expert(self):
        assert SkillLevel.EXPERT == "expert"

    # SkillDomain (5)
    def test_domain_infrastructure(self):
        assert SkillDomain.INFRASTRUCTURE == "infrastructure"

    def test_domain_observability(self):
        assert SkillDomain.OBSERVABILITY == "observability"

    def test_domain_security(self):
        assert SkillDomain.SECURITY == "security"

    def test_domain_database(self):
        assert SkillDomain.DATABASE == "database"

    def test_domain_networking(self):
        assert SkillDomain.NETWORKING == "networking"

    # GapSeverity (5)
    def test_gap_covered(self):
        assert GapSeverity.COVERED == "covered"

    def test_gap_thin(self):
        assert GapSeverity.THIN == "thin"

    def test_gap_at_risk(self):
        assert GapSeverity.AT_RISK == "at_risk"

    def test_gap_critical(self):
        assert GapSeverity.CRITICAL_GAP == "critical_gap"

    def test_gap_no_coverage(self):
        assert GapSeverity.NO_COVERAGE == "no_coverage"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_skill_entry_defaults(self):
        e = SkillEntry()
        assert e.id
        assert e.member_name == ""
        assert e.team == ""
        assert e.skill_name == ""
        assert e.domain == SkillDomain.INFRASTRUCTURE
        assert e.level == SkillLevel.NOVICE
        assert e.last_assessed > 0
        assert e.certifications == []
        assert e.created_at > 0

    def test_skill_gap_defaults(self):
        g = SkillGap()
        assert g.domain == SkillDomain.INFRASTRUCTURE
        assert g.skill_name == ""
        assert g.required_level == SkillLevel.INTERMEDIATE
        assert g.current_max_level == SkillLevel.NOVICE
        assert g.gap_severity == GapSeverity.NO_COVERAGE
        assert g.team == ""
        assert g.members_with_skill == 0
        assert g.created_at > 0

    def test_skill_matrix_report_defaults(self):
        r = SkillMatrixReport()
        assert r.total_members == 0
        assert r.total_skills == 0
        assert r.total_gaps == 0
        assert r.avg_skill_level == 0.0
        assert r.by_domain == {}
        assert r.by_level == {}
        assert r.critical_gaps == []
        assert r.training_recommendations == []
        assert r.generated_at > 0


# ---------------------------------------------------------------------------
# register_skill
# ---------------------------------------------------------------------------


class TestRegisterSkill:
    def test_basic_register(self):
        eng = _engine()
        entry = eng.register_skill(
            member_name="alice",
            team="platform",
            skill_name="Kubernetes",
            domain=SkillDomain.INFRASTRUCTURE,
            level=SkillLevel.ADVANCED,
            certifications=["CKA"],
        )
        assert entry.member_name == "alice"
        assert entry.team == "platform"
        assert entry.skill_name == "Kubernetes"
        assert entry.domain == SkillDomain.INFRASTRUCTURE
        assert entry.level == SkillLevel.ADVANCED
        assert entry.certifications == ["CKA"]

    def test_eviction_at_max(self):
        eng = _engine(max_entries=3)
        for i in range(5):
            eng.register_skill(member_name=f"user-{i}")
        assert len(eng._items) == 3

    def test_defaults(self):
        eng = _engine()
        entry = eng.register_skill(member_name="bob")
        assert entry.level == SkillLevel.NOVICE
        assert entry.domain == SkillDomain.INFRASTRUCTURE
        assert entry.certifications == []


# ---------------------------------------------------------------------------
# get_skill
# ---------------------------------------------------------------------------


class TestGetSkill:
    def test_found(self):
        eng = _engine()
        entry = eng.register_skill(member_name="alice")
        assert eng.get_skill(entry.id) is not None
        assert eng.get_skill(entry.id).member_name == "alice"

    def test_not_found(self):
        eng = _engine()
        assert eng.get_skill("nonexistent") is None


# ---------------------------------------------------------------------------
# list_skills
# ---------------------------------------------------------------------------


class TestListSkills:
    def test_list_all(self):
        eng = _engine()
        eng.register_skill(member_name="alice")
        eng.register_skill(member_name="bob")
        assert len(eng.list_skills()) == 2

    def test_filter_by_member(self):
        eng = _engine()
        eng.register_skill(member_name="alice")
        eng.register_skill(member_name="bob")
        results = eng.list_skills(member_name="alice")
        assert len(results) == 1
        assert results[0].member_name == "alice"

    def test_filter_by_team(self):
        eng = _engine()
        eng.register_skill(member_name="alice", team="platform")
        eng.register_skill(member_name="bob", team="security")
        results = eng.list_skills(team="platform")
        assert len(results) == 1

    def test_filter_by_domain(self):
        eng = _engine()
        eng.register_skill(
            member_name="alice",
            domain=SkillDomain.SECURITY,
        )
        eng.register_skill(
            member_name="bob",
            domain=SkillDomain.DATABASE,
        )
        results = eng.list_skills(domain=SkillDomain.SECURITY)
        assert len(results) == 1


# ---------------------------------------------------------------------------
# assess_skill
# ---------------------------------------------------------------------------


class TestAssessSkill:
    def test_upgrade_level(self):
        eng = _engine()
        entry = eng.register_skill(
            member_name="alice",
            level=SkillLevel.BEGINNER,
        )
        result = eng.assess_skill(entry.id, SkillLevel.ADVANCED)
        assert result is not None
        assert result.level == SkillLevel.ADVANCED

    def test_assess_nonexistent(self):
        eng = _engine()
        assert eng.assess_skill("bogus", SkillLevel.EXPERT) is None


# ---------------------------------------------------------------------------
# identify_skill_gaps
# ---------------------------------------------------------------------------


class TestIdentifySkillGaps:
    def test_critical_gap(self):
        eng = _engine()
        eng.register_skill(
            member_name="alice",
            team="platform",
            skill_name="Terraform",
            domain=SkillDomain.INFRASTRUCTURE,
            level=SkillLevel.NOVICE,
        )
        gaps = eng.identify_skill_gaps(team="platform")
        assert len(gaps) >= 1
        tf_gaps = [g for g in gaps if g.skill_name == "Terraform"]
        assert len(tf_gaps) == 1
        assert tf_gaps[0].gap_severity == GapSeverity.CRITICAL_GAP

    def test_covered_skill(self):
        eng = _engine(min_coverage_per_domain=1)
        eng.register_skill(
            member_name="alice",
            team="platform",
            skill_name="K8s",
            domain=SkillDomain.INFRASTRUCTURE,
            level=SkillLevel.EXPERT,
        )
        eng.register_skill(
            member_name="bob",
            team="platform",
            skill_name="K8s",
            domain=SkillDomain.INFRASTRUCTURE,
            level=SkillLevel.ADVANCED,
        )
        gaps = eng.identify_skill_gaps(team="platform")
        k8s_gaps = [g for g in gaps if g.skill_name == "K8s"]
        assert len(k8s_gaps) == 1
        assert k8s_gaps[0].gap_severity == GapSeverity.COVERED

    def test_at_risk_single_member(self):
        eng = _engine(min_coverage_per_domain=2)
        eng.register_skill(
            member_name="alice",
            team="platform",
            skill_name="Prometheus",
            domain=SkillDomain.OBSERVABILITY,
            level=SkillLevel.EXPERT,
        )
        gaps = eng.identify_skill_gaps(team="platform")
        prom_gaps = [g for g in gaps if g.skill_name == "Prometheus"]
        assert len(prom_gaps) == 1
        assert prom_gaps[0].gap_severity == GapSeverity.AT_RISK


# ---------------------------------------------------------------------------
# calculate_team_coverage
# ---------------------------------------------------------------------------


class TestCalculateTeamCoverage:
    def test_partial_coverage(self):
        eng = _engine()
        eng.register_skill(
            member_name="alice",
            team="platform",
            domain=SkillDomain.INFRASTRUCTURE,
        )
        eng.register_skill(
            member_name="bob",
            team="platform",
            domain=SkillDomain.SECURITY,
        )
        result = eng.calculate_team_coverage("platform")
        assert result["team"] == "platform"
        assert result["total_members"] == 2
        assert result["domains_covered"] == 2
        assert result["coverage_pct"] == 40.0  # 2/5 domains

    def test_empty_team(self):
        eng = _engine()
        result = eng.calculate_team_coverage("ghost")
        assert result["total_members"] == 0
        assert result["coverage_pct"] == 0.0


# ---------------------------------------------------------------------------
# find_single_points_of_failure
# ---------------------------------------------------------------------------


class TestFindSinglePointsOfFailure:
    def test_spof_detected(self):
        eng = _engine()
        eng.register_skill(
            member_name="alice",
            team="platform",
            skill_name="Terraform",
            domain=SkillDomain.INFRASTRUCTURE,
        )
        spofs = eng.find_single_points_of_failure(team="platform")
        assert len(spofs) >= 1
        assert spofs[0]["sole_member"] == "alice"
        assert spofs[0]["skill_name"] == "Terraform"

    def test_no_spof(self):
        eng = _engine()
        eng.register_skill(
            member_name="alice",
            team="platform",
            skill_name="K8s",
            domain=SkillDomain.INFRASTRUCTURE,
        )
        eng.register_skill(
            member_name="bob",
            team="platform",
            skill_name="K8s",
            domain=SkillDomain.INFRASTRUCTURE,
        )
        spofs = eng.find_single_points_of_failure(team="platform")
        k8s_spofs = [s for s in spofs if s["skill_name"] == "K8s"]
        assert len(k8s_spofs) == 0


# ---------------------------------------------------------------------------
# recommend_training
# ---------------------------------------------------------------------------


class TestRecommendTraining:
    def test_training_for_gaps(self):
        eng = _engine()
        eng.register_skill(
            member_name="alice",
            team="platform",
            skill_name="Firewall",
            domain=SkillDomain.SECURITY,
            level=SkillLevel.NOVICE,
        )
        recs = eng.recommend_training(team="platform")
        assert len(recs) >= 1
        fw_recs = [r for r in recs if r["skill_name"] == "Firewall"]
        assert len(fw_recs) == 1
        assert fw_recs[0]["gap_severity"] == "critical_gap"
        assert "Train team" in fw_recs[0]["action"]

    def test_no_training_needed(self):
        eng = _engine(min_coverage_per_domain=1)
        eng.register_skill(
            member_name="alice",
            team="platform",
            skill_name="K8s",
            domain=SkillDomain.INFRASTRUCTURE,
            level=SkillLevel.EXPERT,
        )
        eng.register_skill(
            member_name="bob",
            team="platform",
            skill_name="K8s",
            domain=SkillDomain.INFRASTRUCTURE,
            level=SkillLevel.ADVANCED,
        )
        recs = eng.recommend_training(team="platform")
        k8s_recs = [r for r in recs if r["skill_name"] == "K8s"]
        assert len(k8s_recs) == 0


# ---------------------------------------------------------------------------
# generate_skill_report
# ---------------------------------------------------------------------------


class TestGenerateSkillReport:
    def test_basic_report(self):
        eng = _engine()
        eng.register_skill(
            member_name="alice",
            team="platform",
            skill_name="K8s",
            domain=SkillDomain.INFRASTRUCTURE,
            level=SkillLevel.EXPERT,
        )
        eng.register_skill(
            member_name="bob",
            team="platform",
            skill_name="SQL",
            domain=SkillDomain.DATABASE,
            level=SkillLevel.INTERMEDIATE,
        )
        report = eng.generate_skill_report()
        assert isinstance(report, SkillMatrixReport)
        assert report.total_members == 2
        assert report.total_skills == 2
        assert report.avg_skill_level > 0
        assert report.by_domain["infrastructure"] == 1
        assert report.by_domain["database"] == 1
        assert report.by_level["expert"] == 1
        assert report.by_level["intermediate"] == 1

    def test_empty_report(self):
        eng = _engine()
        report = eng.generate_skill_report()
        assert report.total_skills == 0
        assert len(report.training_recommendations) >= 1

    def test_report_with_critical_gaps(self):
        eng = _engine()
        eng.register_skill(
            member_name="alice",
            skill_name="Novice skill",
            domain=SkillDomain.SECURITY,
            level=SkillLevel.NOVICE,
        )
        report = eng.generate_skill_report()
        assert len(report.critical_gaps) >= 1


# ---------------------------------------------------------------------------
# clear_data
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears_all(self):
        eng = _engine()
        eng.register_skill(member_name="alice")
        eng.identify_skill_gaps()
        eng.clear_data()
        assert len(eng._items) == 0
        assert len(eng._gaps) == 0


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_entries"] == 0
        assert stats["total_gaps"] == 0
        assert stats["unique_members"] == 0
        assert stats["unique_teams"] == 0
        assert stats["domains"] == []

    def test_populated(self):
        eng = _engine()
        eng.register_skill(
            member_name="alice",
            team="platform",
            domain=SkillDomain.INFRASTRUCTURE,
        )
        eng.register_skill(
            member_name="bob",
            team="security",
            domain=SkillDomain.SECURITY,
        )
        stats = eng.get_stats()
        assert stats["total_entries"] == 2
        assert stats["unique_members"] == 2
        assert stats["unique_teams"] == 2
        assert "infrastructure" in stats["domains"]
        assert "security" in stats["domains"]
