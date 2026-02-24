"""Alert Rule Linter — lint and validate alert rules for common issues."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class LintSeverity(StrEnum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    SUGGESTION = "suggestion"
    IGNORED = "ignored"


class LintCategory(StrEnum):
    MISSING_LABEL = "missing_label"
    BAD_THRESHOLD = "bad_threshold"
    NO_RUNBOOK = "no_runbook"
    DUPLICATE_RULE = "duplicate_rule"
    OVERLY_BROAD = "overly_broad"


class RuleType(StrEnum):
    METRIC_THRESHOLD = "metric_threshold"
    LOG_PATTERN = "log_pattern"
    APM_CONDITION = "apm_condition"
    COMPOSITE = "composite"
    STATIC = "static"


# --- Models ---


class AlertRule(BaseModel):
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
    )
    name: str = ""
    rule_type: RuleType = RuleType.METRIC_THRESHOLD
    expression: str = ""
    threshold: float = 0.0
    labels: dict[str, str] = Field(default_factory=dict)
    runbook_url: str = ""
    service_name: str = ""
    is_enabled: bool = True
    created_at: float = Field(default_factory=time.time)


class LintFinding(BaseModel):
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
    )
    rule_id: str = ""
    severity: LintSeverity = LintSeverity.INFO
    category: LintCategory = LintCategory.MISSING_LABEL
    message: str = ""
    suggestion: str = ""
    auto_fixable: bool = False
    created_at: float = Field(default_factory=time.time)


class LintReport(BaseModel):
    total_rules: int = 0
    total_findings: int = 0
    by_severity: dict[str, int] = Field(default_factory=dict)
    by_category: dict[str, int] = Field(default_factory=dict)
    auto_fixable_count: int = 0
    clean_rules_pct: float = 0.0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Linter ---


class AlertRuleLinter:
    """Lint and validate alert rules for common issues."""

    def __init__(
        self,
        max_rules: int = 100000,
        min_quality_score: float = 80.0,
    ) -> None:
        self._max_rules = max_rules
        self._min_quality_score = min_quality_score
        self._items: list[AlertRule] = []
        self._findings: list[LintFinding] = []
        logger.info(
            "alert_rule_linter.initialized",
            max_rules=max_rules,
            min_quality_score=min_quality_score,
        )

    # -- register --

    def register_rule(
        self,
        name: str,
        rule_type: RuleType = RuleType.METRIC_THRESHOLD,
        expression: str = "",
        threshold: float = 0.0,
        labels: dict[str, str] | None = None,
        runbook_url: str = "",
        service_name: str = "",
        is_enabled: bool = True,
        **kw: Any,
    ) -> AlertRule:
        """Register an alert rule for linting."""
        rule = AlertRule(
            name=name,
            rule_type=rule_type,
            expression=expression,
            threshold=threshold,
            labels=labels or {},
            runbook_url=runbook_url,
            service_name=service_name,
            is_enabled=is_enabled,
            **kw,
        )
        self._items.append(rule)
        if len(self._items) > self._max_rules:
            self._items = self._items[-self._max_rules :]
        logger.info(
            "alert_rule_linter.rule_registered",
            rule_id=rule.id,
            name=name,
        )
        return rule

    # -- get / list --

    def get_rule(self, rule_id: str) -> AlertRule | None:
        """Get a single rule by ID."""
        for item in self._items:
            if item.id == rule_id:
                return item
        return None

    def list_rules(
        self,
        service_name: str | None = None,
        rule_type: RuleType | None = None,
        limit: int = 50,
    ) -> list[AlertRule]:
        """List rules with optional filters."""
        results = list(self._items)
        if service_name is not None:
            results = [r for r in results if r.service_name == service_name]
        if rule_type is not None:
            results = [r for r in results if r.rule_type == rule_type]
        return results[-limit:]

    # -- domain operations --

    def lint_rule(self, rule_id: str) -> list[LintFinding]:
        """Lint a single rule and return findings."""
        rule = self.get_rule(rule_id)
        if rule is None:
            return []
        findings: list[LintFinding] = []
        # Check missing labels
        if not rule.labels:
            findings.append(
                LintFinding(
                    rule_id=rule.id,
                    severity=LintSeverity.WARNING,
                    category=LintCategory.MISSING_LABEL,
                    message=f"Rule '{rule.name}' has no labels",
                    suggestion="Add severity/team labels",
                    auto_fixable=False,
                )
            )
        required = {"severity", "team"}
        missing = required - set(rule.labels.keys())
        if missing and rule.labels:
            findings.append(
                LintFinding(
                    rule_id=rule.id,
                    severity=LintSeverity.WARNING,
                    category=LintCategory.MISSING_LABEL,
                    message=(f"Rule '{rule.name}' missing labels: {', '.join(sorted(missing))}"),
                    suggestion="Add required labels",
                    auto_fixable=True,
                )
            )
        # Check runbook
        if not rule.runbook_url:
            findings.append(
                LintFinding(
                    rule_id=rule.id,
                    severity=LintSeverity.ERROR,
                    category=LintCategory.NO_RUNBOOK,
                    message=(f"Rule '{rule.name}' has no runbook URL"),
                    suggestion="Add a runbook link",
                    auto_fixable=False,
                )
            )
        # Check threshold
        if rule.threshold <= 0 and rule.rule_type in (
            RuleType.METRIC_THRESHOLD,
            RuleType.STATIC,
        ):
            findings.append(
                LintFinding(
                    rule_id=rule.id,
                    severity=LintSeverity.ERROR,
                    category=LintCategory.BAD_THRESHOLD,
                    message=(f"Rule '{rule.name}' has non-positive threshold"),
                    suggestion="Set a meaningful threshold",
                    auto_fixable=False,
                )
            )
        # Check overly broad
        if not rule.service_name and not rule.expression:
            findings.append(
                LintFinding(
                    rule_id=rule.id,
                    severity=LintSeverity.SUGGESTION,
                    category=LintCategory.OVERLY_BROAD,
                    message=(f"Rule '{rule.name}' has no service scope or expression"),
                    suggestion="Scope the rule to a service",
                    auto_fixable=False,
                )
            )
        self._findings.extend(findings)
        logger.info(
            "alert_rule_linter.rule_linted",
            rule_id=rule_id,
            findings=len(findings),
        )
        return findings

    def lint_all_rules(self) -> list[LintFinding]:
        """Lint all registered rules."""
        all_findings: list[LintFinding] = []
        for rule in self._items:
            findings = self.lint_rule(rule.id)
            all_findings.extend(findings)
        return all_findings

    def auto_fix_rule(
        self,
        rule_id: str,
    ) -> AlertRule | None:
        """Apply auto-fixes to a rule where possible."""
        rule = self.get_rule(rule_id)
        if rule is None:
            return None
        fixed = False
        # Auto-add missing required labels
        if "severity" not in rule.labels:
            rule.labels["severity"] = "warning"
            fixed = True
        if "team" not in rule.labels:
            rule.labels["team"] = "unassigned"
            fixed = True
        if fixed:
            logger.info(
                "alert_rule_linter.rule_auto_fixed",
                rule_id=rule_id,
            )
        return rule

    def detect_duplicate_rules(
        self,
    ) -> list[dict[str, Any]]:
        """Detect rules with duplicate names or expressions."""
        duplicates: list[dict[str, Any]] = []
        seen_names: dict[str, list[str]] = {}
        for rule in self._items:
            key = rule.name.lower().strip()
            seen_names.setdefault(key, []).append(rule.id)
        for name, ids in sorted(seen_names.items()):
            if len(ids) > 1:
                duplicates.append({"name": name, "rule_ids": ids})
        # Also add findings for duplicates
        for dup in duplicates:
            for rid in dup["rule_ids"]:
                self._findings.append(
                    LintFinding(
                        rule_id=rid,
                        severity=LintSeverity.WARNING,
                        category=LintCategory.DUPLICATE_RULE,
                        message=(f"Duplicate rule name: '{dup['name']}'"),
                        suggestion="Remove or rename duplicate",
                        auto_fixable=False,
                    )
                )
        return duplicates

    def calculate_rule_quality_score(
        self,
    ) -> float:
        """Calculate overall rule quality score (0-100)."""
        if not self._items:
            return 100.0
        total = len(self._items)
        # Run lint on all rules
        findings = self.lint_all_rules()
        error_count = sum(1 for f in findings if f.severity == LintSeverity.ERROR)
        warn_count = sum(1 for f in findings if f.severity == LintSeverity.WARNING)
        # Deductions: errors=10pts, warnings=3pts
        deductions = (error_count * 10) + (warn_count * 3)
        max_score = total * 10
        if max_score == 0:
            return 100.0
        score = max(
            0.0,
            round((1 - deductions / max_score) * 100, 2),
        )
        logger.info(
            "alert_rule_linter.quality_score",
            score=score,
            errors=error_count,
            warnings=warn_count,
        )
        return score

    # -- report --

    def generate_lint_report(self) -> LintReport:
        """Generate a comprehensive lint report."""
        findings = self.lint_all_rules()
        by_severity: dict[str, int] = {}
        for f in findings:
            key = f.severity.value
            by_severity[key] = by_severity.get(key, 0) + 1
        by_category: dict[str, int] = {}
        for f in findings:
            key = f.category.value
            by_category[key] = by_category.get(key, 0) + 1
        auto_fixable = sum(1 for f in findings if f.auto_fixable)
        rules_with_findings = {f.rule_id for f in findings}
        total = len(self._items)
        clean = total - len(rules_with_findings)
        clean_pct = round(clean / total * 100, 2) if total else 0.0
        recs = self._build_recommendations(findings, total)
        return LintReport(
            total_rules=total,
            total_findings=len(findings),
            by_severity=by_severity,
            by_category=by_category,
            auto_fixable_count=auto_fixable,
            clean_rules_pct=clean_pct,
            recommendations=recs,
        )

    # -- housekeeping --

    def clear_data(self) -> int:
        """Clear all rules and findings. Returns count."""
        count = len(self._items)
        self._items.clear()
        self._findings.clear()
        logger.info("alert_rule_linter.cleared", count=count)
        return count

    def get_stats(self) -> dict[str, Any]:
        """Return summary statistics."""
        type_dist: dict[str, int] = {}
        for r in self._items:
            key = r.rule_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        enabled = sum(1 for r in self._items if r.is_enabled)
        return {
            "total_rules": len(self._items),
            "total_findings": len(self._findings),
            "enabled_rules": enabled,
            "min_quality_score": self._min_quality_score,
            "type_distribution": type_dist,
        }

    # -- internal helpers --

    def _build_recommendations(
        self,
        findings: list[LintFinding],
        total_rules: int,
    ) -> list[str]:
        recs: list[str] = []
        errors = sum(1 for f in findings if f.severity == LintSeverity.ERROR)
        no_runbook = sum(1 for f in findings if f.category == LintCategory.NO_RUNBOOK)
        if errors:
            recs.append(f"{errors} error(s) found - fix before deploying")
        if no_runbook:
            recs.append(f"{no_runbook} rule(s) missing runbook links")
        if not recs:
            recs.append("All rules pass lint checks")
        return recs
