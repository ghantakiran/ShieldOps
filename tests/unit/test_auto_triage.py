"""Tests for shieldops.incidents.auto_triage — IncidentAutoTriageEngine."""

from __future__ import annotations

from shieldops.incidents.auto_triage import (
    AutoTriageReport,
    IncidentAutoTriageEngine,
    TriageCategory,
    TriageConfidence,
    TriagePriority,
    TriageRecord,
    TriageRule,
)


def _engine(**kw) -> IncidentAutoTriageEngine:
    return IncidentAutoTriageEngine(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # TriageCategory (5)
    def test_cat_infrastructure(self):
        assert TriageCategory.INFRASTRUCTURE == "infrastructure"

    def test_cat_application(self):
        assert TriageCategory.APPLICATION == "application"

    def test_cat_network(self):
        assert TriageCategory.NETWORK == "network"

    def test_cat_security(self):
        assert TriageCategory.SECURITY == "security"

    def test_cat_data(self):
        assert TriageCategory.DATA == "data"

    # TriagePriority (5)
    def test_pri_p1_critical(self):
        assert TriagePriority.P1_CRITICAL == "p1_critical"

    def test_pri_p2_high(self):
        assert TriagePriority.P2_HIGH == "p2_high"

    def test_pri_p3_medium(self):
        assert TriagePriority.P3_MEDIUM == "p3_medium"

    def test_pri_p4_low(self):
        assert TriagePriority.P4_LOW == "p4_low"

    def test_pri_p5_informational(self):
        assert TriagePriority.P5_INFORMATIONAL == "p5_informational"

    # TriageConfidence (5)
    def test_conf_high(self):
        assert TriageConfidence.HIGH == "high"

    def test_conf_medium(self):
        assert TriageConfidence.MEDIUM == "medium"

    def test_conf_low(self):
        assert TriageConfidence.LOW == "low"

    def test_conf_uncertain(self):
        assert TriageConfidence.UNCERTAIN == "uncertain"

    def test_conf_manual_required(self):
        assert TriageConfidence.MANUAL_REQUIRED == "manual_required"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_triage_record_defaults(self):
        r = TriageRecord()
        assert r.id
        assert r.incident_id == ""
        assert r.category == TriageCategory.APPLICATION
        assert r.priority == TriagePriority.P3_MEDIUM
        assert r.confidence == TriageConfidence.MEDIUM
        assert r.assigned_team == ""
        assert r.triage_time_seconds == 0.0
        assert r.details == ""
        assert r.created_at > 0

    def test_triage_rule_defaults(self):
        r = TriageRule()
        assert r.id
        assert r.rule_name == ""
        assert r.category == TriageCategory.APPLICATION
        assert r.priority == TriagePriority.P3_MEDIUM
        assert r.match_pattern == ""
        assert r.hit_count == 0
        assert r.created_at > 0

    def test_auto_triage_report_defaults(self):
        r = AutoTriageReport()
        assert r.total_triages == 0
        assert r.total_rules == 0
        assert r.avg_triage_time_seconds == 0.0
        assert r.by_category == {}
        assert r.by_priority == {}
        assert r.misclassified_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_triage
# -------------------------------------------------------------------


class TestRecordTriage:
    def test_basic(self):
        eng = _engine()
        r = eng.record_triage(
            "inc-1",
            category=TriageCategory.INFRASTRUCTURE,
            priority=TriagePriority.P1_CRITICAL,
        )
        assert r.incident_id == "inc-1"
        assert r.category == TriageCategory.INFRASTRUCTURE
        assert r.confidence == TriageConfidence.HIGH

    def test_auto_confidence_p3(self):
        eng = _engine()
        r = eng.record_triage("inc-2", priority=TriagePriority.P3_MEDIUM)
        assert r.confidence == TriageConfidence.MEDIUM

    def test_auto_confidence_p4(self):
        eng = _engine()
        r = eng.record_triage("inc-3", priority=TriagePriority.P4_LOW)
        assert r.confidence == TriageConfidence.LOW

    def test_explicit_confidence(self):
        eng = _engine()
        r = eng.record_triage("inc-4", confidence=TriageConfidence.UNCERTAIN)
        assert r.confidence == TriageConfidence.UNCERTAIN

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_triage(f"inc-{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_triage
# -------------------------------------------------------------------


class TestGetTriage:
    def test_found(self):
        eng = _engine()
        r = eng.record_triage("inc-1")
        assert eng.get_triage(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_triage("nonexistent") is None


# -------------------------------------------------------------------
# list_triages
# -------------------------------------------------------------------


class TestListTriages:
    def test_list_all(self):
        eng = _engine()
        eng.record_triage("inc-1")
        eng.record_triage("inc-2")
        assert len(eng.list_triages()) == 2

    def test_filter_by_incident_id(self):
        eng = _engine()
        eng.record_triage("inc-1")
        eng.record_triage("inc-2")
        results = eng.list_triages(incident_id="inc-1")
        assert len(results) == 1

    def test_filter_by_category(self):
        eng = _engine()
        eng.record_triage("inc-1", category=TriageCategory.NETWORK)
        eng.record_triage("inc-2", category=TriageCategory.SECURITY)
        results = eng.list_triages(category=TriageCategory.NETWORK)
        assert len(results) == 1


# -------------------------------------------------------------------
# add_rule
# -------------------------------------------------------------------


class TestAddRule:
    def test_basic(self):
        eng = _engine()
        rule = eng.add_rule(
            "cpu-spike-rule",
            category=TriageCategory.INFRASTRUCTURE,
            priority=TriagePriority.P2_HIGH,
            match_pattern="cpu.*spike",
            hit_count=42,
        )
        assert rule.rule_name == "cpu-spike-rule"
        assert rule.hit_count == 42

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_rule(f"rule-{i}")
        assert len(eng._rules) == 2


# -------------------------------------------------------------------
# analyze_triage_accuracy
# -------------------------------------------------------------------


class TestAnalyzeTriageAccuracy:
    def test_with_data(self):
        eng = _engine()
        eng.record_triage(
            "inc-1",
            category=TriageCategory.NETWORK,
            priority=TriagePriority.P2_HIGH,
        )
        result = eng.analyze_triage_accuracy("inc-1")
        assert result["incident_id"] == "inc-1"
        assert result["category"] == "network"

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_triage_accuracy("ghost")
        assert result["status"] == "no_data"


# -------------------------------------------------------------------
# identify_misclassified
# -------------------------------------------------------------------


class TestIdentifyMisclassified:
    def test_with_low_confidence(self):
        eng = _engine()
        eng.record_triage("inc-1", confidence=TriageConfidence.HIGH)
        eng.record_triage("inc-2", confidence=TriageConfidence.LOW)
        eng.record_triage("inc-3", confidence=TriageConfidence.UNCERTAIN)
        results = eng.identify_misclassified()
        assert len(results) == 2

    def test_empty(self):
        eng = _engine()
        assert eng.identify_misclassified() == []


# -------------------------------------------------------------------
# rank_rules_by_hit_rate
# -------------------------------------------------------------------


class TestRankRulesByHitRate:
    def test_with_data(self):
        eng = _engine()
        eng.add_rule("rule-a", hit_count=10)
        eng.add_rule("rule-b", hit_count=50)
        eng.add_rule("rule-c", hit_count=25)
        results = eng.rank_rules_by_hit_rate()
        assert results[0]["rule_name"] == "rule-b"
        assert results[0]["hit_count"] == 50

    def test_empty(self):
        eng = _engine()
        assert eng.rank_rules_by_hit_rate() == []


# -------------------------------------------------------------------
# detect_category_drift
# -------------------------------------------------------------------


class TestDetectCategoryDrift:
    def test_with_data(self):
        eng = _engine()
        for _ in range(5):
            eng.record_triage("inc", category=TriageCategory.NETWORK)
        for _ in range(5):
            eng.record_triage("inc", category=TriageCategory.SECURITY)
        results = eng.detect_category_drift()
        assert len(results) >= 1

    def test_empty(self):
        eng = _engine()
        assert eng.detect_category_drift() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine()
        eng.record_triage(
            "inc-1",
            category=TriageCategory.INFRASTRUCTURE,
            priority=TriagePriority.P1_CRITICAL,
        )
        eng.record_triage("inc-2", confidence=TriageConfidence.LOW)
        eng.add_rule("rule-1")
        report = eng.generate_report()
        assert report.total_triages == 2
        assert report.total_rules == 1
        assert report.by_category != {}
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_triages == 0
        assert "meets targets" in report.recommendations[0]


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_triage("inc-1")
        eng.add_rule("rule-1")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._rules) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_triages"] == 0
        assert stats["total_rules"] == 0
        assert stats["category_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_triage("inc-1", category=TriageCategory.NETWORK)
        eng.record_triage("inc-2", category=TriageCategory.SECURITY)
        eng.add_rule("rule-1")
        stats = eng.get_stats()
        assert stats["total_triages"] == 2
        assert stats["total_rules"] == 1
        assert stats["unique_incidents"] == 2
