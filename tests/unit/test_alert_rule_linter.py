"""Tests for shieldops.observability.alert_rule_linter — AlertRuleLinter."""

from __future__ import annotations

from shieldops.observability.alert_rule_linter import (
    AlertRule,
    AlertRuleLinter,
    LintCategory,
    LintFinding,
    LintReport,
    LintSeverity,
    RuleType,
)


def _engine(**kw) -> AlertRuleLinter:
    return AlertRuleLinter(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # LintSeverity (5 values)

    def test_lint_severity_error(self):
        assert LintSeverity.ERROR == "error"

    def test_lint_severity_warning(self):
        assert LintSeverity.WARNING == "warning"

    def test_lint_severity_info(self):
        assert LintSeverity.INFO == "info"

    def test_lint_severity_suggestion(self):
        assert LintSeverity.SUGGESTION == "suggestion"

    def test_lint_severity_ignored(self):
        assert LintSeverity.IGNORED == "ignored"

    # LintCategory (5 values)

    def test_lint_category_missing_label(self):
        assert LintCategory.MISSING_LABEL == "missing_label"

    def test_lint_category_bad_threshold(self):
        assert LintCategory.BAD_THRESHOLD == "bad_threshold"

    def test_lint_category_no_runbook(self):
        assert LintCategory.NO_RUNBOOK == "no_runbook"

    def test_lint_category_duplicate_rule(self):
        assert LintCategory.DUPLICATE_RULE == "duplicate_rule"

    def test_lint_category_overly_broad(self):
        assert LintCategory.OVERLY_BROAD == "overly_broad"

    # RuleType (5 values)

    def test_rule_type_metric_threshold(self):
        assert RuleType.METRIC_THRESHOLD == "metric_threshold"

    def test_rule_type_log_pattern(self):
        assert RuleType.LOG_PATTERN == "log_pattern"

    def test_rule_type_apm_condition(self):
        assert RuleType.APM_CONDITION == "apm_condition"

    def test_rule_type_composite(self):
        assert RuleType.COMPOSITE == "composite"

    def test_rule_type_static(self):
        assert RuleType.STATIC == "static"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_alert_rule_defaults(self):
        rule = AlertRule()
        assert rule.id
        assert rule.name == ""
        assert rule.rule_type == RuleType.METRIC_THRESHOLD
        assert rule.expression == ""
        assert rule.threshold == 0.0
        assert rule.labels == {}
        assert rule.runbook_url == ""
        assert rule.service_name == ""
        assert rule.is_enabled is True
        assert rule.created_at > 0

    def test_lint_finding_defaults(self):
        finding = LintFinding()
        assert finding.id
        assert finding.rule_id == ""
        assert finding.severity == LintSeverity.INFO
        assert finding.category == LintCategory.MISSING_LABEL
        assert finding.message == ""
        assert finding.suggestion == ""
        assert finding.auto_fixable is False
        assert finding.created_at > 0

    def test_lint_report_defaults(self):
        report = LintReport()
        assert report.total_rules == 0
        assert report.total_findings == 0
        assert report.by_severity == {}
        assert report.by_category == {}
        assert report.auto_fixable_count == 0
        assert report.clean_rules_pct == 0.0
        assert report.recommendations == []
        assert report.generated_at > 0


# -------------------------------------------------------------------
# register_rule
# -------------------------------------------------------------------


class TestRegisterRule:
    def test_basic_register(self):
        eng = _engine()
        rule = eng.register_rule("high-cpu")
        assert rule.name == "high-cpu"
        assert len(eng.list_rules()) == 1

    def test_register_assigns_unique_ids(self):
        eng = _engine()
        r1 = eng.register_rule("rule-a")
        r2 = eng.register_rule("rule-b")
        assert r1.id != r2.id

    def test_register_with_params(self):
        eng = _engine()
        rule = eng.register_rule(
            "disk-full",
            rule_type=RuleType.STATIC,
            threshold=90.0,
            labels={"severity": "critical"},
            runbook_url="https://wiki/disk",
            service_name="storage-svc",
        )
        assert rule.rule_type == RuleType.STATIC
        assert rule.threshold == 90.0
        assert rule.labels["severity"] == "critical"
        assert rule.runbook_url == "https://wiki/disk"

    def test_eviction_at_max_rules(self):
        eng = _engine(max_rules=3)
        ids = []
        for i in range(4):
            rule = eng.register_rule(f"rule-{i}")
            ids.append(rule.id)
        rules = eng.list_rules(limit=100)
        assert len(rules) == 3
        found = {r.id for r in rules}
        assert ids[0] not in found
        assert ids[3] in found


# -------------------------------------------------------------------
# get_rule
# -------------------------------------------------------------------


class TestGetRule:
    def test_get_existing(self):
        eng = _engine()
        rule = eng.register_rule("test-rule")
        found = eng.get_rule(rule.id)
        assert found is not None
        assert found.id == rule.id

    def test_get_not_found(self):
        eng = _engine()
        assert eng.get_rule("nonexistent") is None


# -------------------------------------------------------------------
# list_rules
# -------------------------------------------------------------------


class TestListRules:
    def test_list_all(self):
        eng = _engine()
        eng.register_rule("r1")
        eng.register_rule("r2")
        eng.register_rule("r3")
        assert len(eng.list_rules()) == 3

    def test_filter_by_service(self):
        eng = _engine()
        eng.register_rule("r1", service_name="svc-a")
        eng.register_rule("r2", service_name="svc-b")
        eng.register_rule("r3", service_name="svc-a")
        results = eng.list_rules(service_name="svc-a")
        assert len(results) == 2
        assert all(r.service_name == "svc-a" for r in results)

    def test_filter_by_rule_type(self):
        eng = _engine()
        eng.register_rule("r1", rule_type=RuleType.STATIC)
        eng.register_rule("r2", rule_type=RuleType.LOG_PATTERN)
        eng.register_rule("r3", rule_type=RuleType.STATIC)
        results = eng.list_rules(rule_type=RuleType.STATIC)
        assert len(results) == 2

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.register_rule(f"rule-{i}")
        results = eng.list_rules(limit=5)
        assert len(results) == 5


# -------------------------------------------------------------------
# lint_rule
# -------------------------------------------------------------------


class TestLintRule:
    def test_clean_rule_no_findings(self):
        eng = _engine()
        rule = eng.register_rule(
            "good-rule",
            threshold=50.0,
            labels={"severity": "warning", "team": "sre"},
            runbook_url="https://wiki/rule",
            service_name="api-svc",
            expression="cpu > 80",
        )
        findings = eng.lint_rule(rule.id)
        assert len(findings) == 0

    def test_missing_labels_finding(self):
        eng = _engine()
        rule = eng.register_rule(
            "no-labels",
            threshold=50.0,
            runbook_url="https://wiki/rule",
            service_name="api",
            expression="cpu > 80",
        )
        findings = eng.lint_rule(rule.id)
        categories = [f.category for f in findings]
        assert LintCategory.MISSING_LABEL in categories

    def test_no_runbook_finding(self):
        eng = _engine()
        rule = eng.register_rule(
            "no-runbook",
            threshold=50.0,
            labels={"severity": "warning", "team": "sre"},
            service_name="api",
            expression="cpu > 80",
        )
        findings = eng.lint_rule(rule.id)
        categories = [f.category for f in findings]
        assert LintCategory.NO_RUNBOOK in categories

    def test_bad_threshold_finding(self):
        eng = _engine()
        rule = eng.register_rule(
            "bad-thresh",
            threshold=0.0,
            rule_type=RuleType.METRIC_THRESHOLD,
            labels={"severity": "warning", "team": "sre"},
            runbook_url="https://wiki/rule",
            service_name="api",
        )
        findings = eng.lint_rule(rule.id)
        categories = [f.category for f in findings]
        assert LintCategory.BAD_THRESHOLD in categories

    def test_nonexistent_rule_returns_empty(self):
        eng = _engine()
        findings = eng.lint_rule("nonexistent")
        assert findings == []


# -------------------------------------------------------------------
# lint_all_rules
# -------------------------------------------------------------------


class TestLintAllRules:
    def test_lint_all(self):
        eng = _engine()
        eng.register_rule("rule-a")
        eng.register_rule("rule-b")
        findings = eng.lint_all_rules()
        assert len(findings) >= 2

    def test_lint_all_empty(self):
        eng = _engine()
        findings = eng.lint_all_rules()
        assert findings == []


# -------------------------------------------------------------------
# auto_fix_rule
# -------------------------------------------------------------------


class TestAutoFixRule:
    def test_auto_fix_adds_labels(self):
        eng = _engine()
        rule = eng.register_rule("needs-fix")
        fixed = eng.auto_fix_rule(rule.id)
        assert fixed is not None
        assert "severity" in fixed.labels
        assert "team" in fixed.labels

    def test_auto_fix_nonexistent(self):
        eng = _engine()
        assert eng.auto_fix_rule("nope") is None

    def test_auto_fix_already_has_labels(self):
        eng = _engine()
        rule = eng.register_rule(
            "has-labels",
            labels={"severity": "critical", "team": "sre"},
        )
        fixed = eng.auto_fix_rule(rule.id)
        assert fixed is not None
        assert fixed.labels["severity"] == "critical"
        assert fixed.labels["team"] == "sre"


# -------------------------------------------------------------------
# detect_duplicate_rules
# -------------------------------------------------------------------


class TestDetectDuplicateRules:
    def test_finds_duplicates(self):
        eng = _engine()
        eng.register_rule("High CPU Alert")
        eng.register_rule("high cpu alert")
        dupes = eng.detect_duplicate_rules()
        assert len(dupes) == 1
        assert len(dupes[0]["rule_ids"]) == 2

    def test_no_duplicates(self):
        eng = _engine()
        eng.register_rule("rule-a")
        eng.register_rule("rule-b")
        dupes = eng.detect_duplicate_rules()
        assert len(dupes) == 0


# -------------------------------------------------------------------
# calculate_rule_quality_score
# -------------------------------------------------------------------


class TestCalculateRuleQualityScore:
    def test_perfect_score(self):
        eng = _engine()
        eng.register_rule(
            "perfect",
            threshold=50.0,
            labels={"severity": "warning", "team": "sre"},
            runbook_url="https://wiki/rule",
            service_name="api",
            expression="cpu > 80",
        )
        score = eng.calculate_rule_quality_score()
        assert score == 100.0

    def test_low_score_with_issues(self):
        eng = _engine()
        eng.register_rule("bad-rule")
        score = eng.calculate_rule_quality_score()
        assert score < 100.0

    def test_empty_returns_100(self):
        eng = _engine()
        score = eng.calculate_rule_quality_score()
        assert score == 100.0


# -------------------------------------------------------------------
# generate_lint_report
# -------------------------------------------------------------------


class TestGenerateLintReport:
    def test_basic_report(self):
        eng = _engine()
        eng.register_rule("rule-a")
        eng.register_rule(
            "rule-b",
            threshold=50.0,
            labels={"severity": "warning", "team": "sre"},
            runbook_url="https://wiki/rule",
            service_name="api",
            expression="cpu > 80",
        )
        report = eng.generate_lint_report()
        assert report.total_rules == 2
        assert report.total_findings >= 1
        assert isinstance(report.by_severity, dict)
        assert isinstance(report.recommendations, list)

    def test_empty_report(self):
        eng = _engine()
        report = eng.generate_lint_report()
        assert report.total_rules == 0
        assert report.total_findings == 0
        assert report.clean_rules_pct == 0.0


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears_all(self):
        eng = _engine()
        eng.register_rule("r1")
        eng.register_rule("r2")
        count = eng.clear_data()
        assert count == 2
        assert len(eng.list_rules()) == 0

    def test_clear_empty(self):
        eng = _engine()
        assert eng.clear_data() == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_stats_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_rules"] == 0
        assert stats["total_findings"] == 0
        assert stats["enabled_rules"] == 0
        assert stats["min_quality_score"] == 80.0
        assert stats["type_distribution"] == {}

    def test_stats_populated(self):
        eng = _engine()
        eng.register_rule(
            "r1",
            rule_type=RuleType.STATIC,
        )
        eng.register_rule(
            "r2",
            rule_type=RuleType.LOG_PATTERN,
        )
        stats = eng.get_stats()
        assert stats["total_rules"] == 2
        assert stats["enabled_rules"] == 2
        assert len(stats["type_distribution"]) == 2
