"""Tests for shieldops.security.ransomware_defense_engine — RansomwareDefenseEngine."""

from __future__ import annotations

from shieldops.security.ransomware_defense_engine import (
    DefenseLayer,
    RansomwareAnalysis,
    RansomwareDefenseEngine,
    RansomwareIndicator,
    RansomwareRecord,
    RansomwareReport,
    ReadinessLevel,
)


def _engine(**kw) -> RansomwareDefenseEngine:
    return RansomwareDefenseEngine(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_ransomwareindicator_mass_encryption(self):
        assert RansomwareIndicator.MASS_ENCRYPTION == "mass_encryption"

    def test_ransomwareindicator_shadow_copy_delete(self):
        assert RansomwareIndicator.SHADOW_COPY_DELETE == "shadow_copy_delete"

    def test_ransomwareindicator_ransom_note(self):
        assert RansomwareIndicator.RANSOM_NOTE == "ransom_note"

    def test_ransomwareindicator_c2_communication(self):
        assert RansomwareIndicator.C2_COMMUNICATION == "c2_communication"

    def test_ransomwareindicator_lateral_spread(self):
        assert RansomwareIndicator.LATERAL_SPREAD == "lateral_spread"

    def test_defenselayer_prevention(self):
        assert DefenseLayer.PREVENTION == "prevention"

    def test_defenselayer_detection(self):
        assert DefenseLayer.DETECTION == "detection"

    def test_defenselayer_containment(self):
        assert DefenseLayer.CONTAINMENT == "containment"

    def test_defenselayer_recovery(self):
        assert DefenseLayer.RECOVERY == "recovery"

    def test_defenselayer_post_incident(self):
        assert DefenseLayer.POST_INCIDENT == "post_incident"

    def test_readinesslevel_excellent(self):
        assert ReadinessLevel.EXCELLENT == "excellent"

    def test_readinesslevel_good(self):
        assert ReadinessLevel.GOOD == "good"

    def test_readinesslevel_adequate(self):
        assert ReadinessLevel.ADEQUATE == "adequate"

    def test_readinesslevel_poor(self):
        assert ReadinessLevel.POOR == "poor"

    def test_readinesslevel_critical(self):
        assert ReadinessLevel.CRITICAL == "critical"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_ransomwarerecord_defaults(self):
        r = RansomwareRecord()
        assert r.id
        assert r.defense_name == ""
        assert r.readiness_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_ransomwareanalysis_defaults(self):
        c = RansomwareAnalysis()
        assert c.id
        assert c.defense_name == ""
        assert c.analysis_score == 0.0
        assert c.threshold == 0.0
        assert c.breached == 0.0
        assert c.description == ""
        assert c.created_at > 0

    def test_ransomwarereport_defaults(self):
        r = RansomwareReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.low_readiness_count == 0
        assert r.avg_readiness_score == 0
        assert r.by_indicator == {}
        assert r.by_layer == {}
        assert r.by_readiness == {}
        assert r.top_low_readiness == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_defense
# ---------------------------------------------------------------------------


class TestRecordDefense:
    def test_basic(self):
        eng = _engine()
        r = eng.record_defense(
            defense_name="test-item",
            ransomware_indicator=RansomwareIndicator.SHADOW_COPY_DELETE,
            readiness_score=92.0,
            service="auth-svc",
            team="security",
        )
        assert r.defense_name == "test-item"
        assert r.readiness_score == 92.0
        assert r.service == "auth-svc"
        assert r.team == "security"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_defense(defense_name=f"ITEM-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_defense
# ---------------------------------------------------------------------------


class TestGetDefense:
    def test_found(self):
        eng = _engine()
        r = eng.record_defense(defense_name="test-item")
        result = eng.get_defense(r.id)
        assert result is not None
        assert result.defense_name == "test-item"

    def test_not_found(self):
        eng = _engine()
        assert eng.get_defense("nonexistent") is None


# ---------------------------------------------------------------------------
# list_defenses
# ---------------------------------------------------------------------------


class TestListDefenses:
    def test_list_all(self):
        eng = _engine()
        eng.record_defense(defense_name="ITEM-001")
        eng.record_defense(defense_name="ITEM-002")
        assert len(eng.list_defenses()) == 2

    def test_filter_by_ransomware_indicator(self):
        eng = _engine()
        eng.record_defense(
            defense_name="ITEM-001", ransomware_indicator=RansomwareIndicator.MASS_ENCRYPTION
        )
        eng.record_defense(
            defense_name="ITEM-002", ransomware_indicator=RansomwareIndicator.SHADOW_COPY_DELETE
        )
        results = eng.list_defenses(ransomware_indicator=RansomwareIndicator.MASS_ENCRYPTION)
        assert len(results) == 1

    def test_filter_by_defense_layer(self):
        eng = _engine()
        eng.record_defense(defense_name="ITEM-001", defense_layer=DefenseLayer.PREVENTION)
        eng.record_defense(defense_name="ITEM-002", defense_layer=DefenseLayer.DETECTION)
        results = eng.list_defenses(defense_layer=DefenseLayer.PREVENTION)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_defense(defense_name="ITEM-001", team="security")
        eng.record_defense(defense_name="ITEM-002", team="platform")
        results = eng.list_defenses(team="security")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_defense(defense_name=f"ITEM-{i}")
        assert len(eng.list_defenses(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            defense_name="test-item",
            analysis_score=88.5,
            threshold=80.0,
            breached=True,
            description="test description",
        )
        assert a.defense_name == "test-item"
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(defense_name=f"ITEM-{i}")
        assert len(eng._analyses) == 2


# ---------------------------------------------------------------------------
# analyze_defense_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_defense(
            defense_name="ITEM-001",
            ransomware_indicator=RansomwareIndicator.MASS_ENCRYPTION,
            readiness_score=90.0,
        )
        eng.record_defense(
            defense_name="ITEM-002",
            ransomware_indicator=RansomwareIndicator.MASS_ENCRYPTION,
            readiness_score=70.0,
        )
        result = eng.analyze_defense_distribution()
        assert "mass_encryption" in result
        assert result["mass_encryption"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_defense_distribution() == {}


# ---------------------------------------------------------------------------
# identify_low_readiness_defenses
# ---------------------------------------------------------------------------


class TestIdentifyProblems:
    def test_detects_threshold(self):
        eng = _engine(readiness_threshold=70.0)
        eng.record_defense(defense_name="ITEM-001", readiness_score=30.0)
        eng.record_defense(defense_name="ITEM-002", readiness_score=90.0)
        results = eng.identify_low_readiness_defenses()
        assert len(results) == 1
        assert results[0]["defense_name"] == "ITEM-001"

    def test_sorted_ascending(self):
        eng = _engine(readiness_threshold=70.0)
        eng.record_defense(defense_name="ITEM-001", readiness_score=50.0)
        eng.record_defense(defense_name="ITEM-002", readiness_score=30.0)
        results = eng.identify_low_readiness_defenses()
        assert len(results) == 2
        assert results[0]["readiness_score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_low_readiness_defenses() == []


# ---------------------------------------------------------------------------
# rank_by_readiness_score
# ---------------------------------------------------------------------------


class TestRankByScore:
    def test_sorted(self):
        eng = _engine()
        eng.record_defense(defense_name="ITEM-001", service="auth-svc", readiness_score=90.0)
        eng.record_defense(defense_name="ITEM-002", service="api-gw", readiness_score=50.0)
        results = eng.rank_by_readiness_score()
        assert len(results) == 2
        assert results[0]["service"] == "api-gw"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_readiness_score() == []


# ---------------------------------------------------------------------------
# detect_readiness_trends
# ---------------------------------------------------------------------------


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(defense_name="ITEM-001", analysis_score=50.0)
        result = eng.detect_readiness_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(defense_name="ITEM-001", analysis_score=20.0)
        eng.add_analysis(defense_name="ITEM-002", analysis_score=20.0)
        eng.add_analysis(defense_name="ITEM-003", analysis_score=80.0)
        eng.add_analysis(defense_name="ITEM-004", analysis_score=80.0)
        result = eng.detect_readiness_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_readiness_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(readiness_threshold=70.0)
        eng.record_defense(defense_name="test-item", readiness_score=30.0)
        report = eng.generate_report()
        assert isinstance(report, RansomwareReport)
        assert report.total_records == 1
        assert report.low_readiness_count == 1
        assert len(report.top_low_readiness) == 1
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
        eng.record_defense(defense_name="ITEM-001")
        eng.add_analysis(defense_name="ITEM-001")
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

    def test_populated(self):
        eng = _engine()
        eng.record_defense(
            defense_name="ITEM-001",
            ransomware_indicator=RansomwareIndicator.MASS_ENCRYPTION,
            service="auth-svc",
            team="security",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
