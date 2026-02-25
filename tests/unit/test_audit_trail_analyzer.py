"""Tests for shieldops.compliance.audit_trail_analyzer — ComplianceAuditTrailAnalyzer."""

from __future__ import annotations

from shieldops.compliance.audit_trail_analyzer import (
    AuditCompletenessScore,
    AuditPatternType,
    AuditScope,
    AuditTrailFinding,
    AuditTrailReport,
    CompletenessLevel,
    ComplianceAuditTrailAnalyzer,
)


def _engine(**kw) -> ComplianceAuditTrailAnalyzer:
    return ComplianceAuditTrailAnalyzer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    # AuditPatternType (5)
    def test_pattern_normal(self):
        assert AuditPatternType.NORMAL == "normal"

    def test_pattern_suspicious_modification(self):
        assert AuditPatternType.SUSPICIOUS_MODIFICATION == "suspicious_modification"

    def test_pattern_privilege_misuse(self):
        assert AuditPatternType.PRIVILEGE_MISUSE == "privilege_misuse"

    def test_pattern_audit_gap(self):
        assert AuditPatternType.AUDIT_GAP == "audit_gap"

    def test_pattern_bulk_change(self):
        assert AuditPatternType.BULK_CHANGE == "bulk_change"

    # CompletenessLevel (5)
    def test_level_complete(self):
        assert CompletenessLevel.COMPLETE == "complete"

    def test_level_mostly_complete(self):
        assert CompletenessLevel.MOSTLY_COMPLETE == "mostly_complete"

    def test_level_partial(self):
        assert CompletenessLevel.PARTIAL == "partial"

    def test_level_sparse(self):
        assert CompletenessLevel.SPARSE == "sparse"

    def test_level_missing(self):
        assert CompletenessLevel.MISSING == "missing"

    # AuditScope (5)
    def test_scope_infrastructure(self):
        assert AuditScope.INFRASTRUCTURE == "infrastructure"

    def test_scope_application(self):
        assert AuditScope.APPLICATION == "application"

    def test_scope_database(self):
        assert AuditScope.DATABASE == "database"

    def test_scope_security(self):
        assert AuditScope.SECURITY == "security"

    def test_scope_compliance(self):
        assert AuditScope.COMPLIANCE == "compliance"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_audit_trail_finding_defaults(self):
        f = AuditTrailFinding()
        assert f.id
        assert f.scope == AuditScope.INFRASTRUCTURE
        assert f.pattern_type == AuditPatternType.NORMAL
        assert f.actor == ""
        assert f.resource == ""
        assert f.description == ""
        assert f.severity_score == 0.0
        assert f.investigated is False
        assert f.created_at > 0

    def test_audit_completeness_score_defaults(self):
        s = AuditCompletenessScore()
        assert s.id
        assert s.scope == AuditScope.INFRASTRUCTURE
        assert s.completeness == CompletenessLevel.COMPLETE
        assert s.completeness_pct == 100.0
        assert s.gap_count == 0
        assert s.total_expected_events == 0
        assert s.total_actual_events == 0
        assert s.created_at > 0

    def test_audit_trail_report_defaults(self):
        r = AuditTrailReport()
        assert r.total_findings == 0
        assert r.suspicious_count == 0
        assert r.avg_completeness_pct == 0.0
        assert r.by_pattern_type == {}
        assert r.by_scope == {}
        assert r.actors_of_concern == []
        assert r.recommendations == []
        assert r.generated_at > 0


# ---------------------------------------------------------------------------
# record_finding
# ---------------------------------------------------------------------------


class TestRecordFinding:
    def test_basic(self):
        eng = _engine()
        f = eng.record_finding(
            scope=AuditScope.INFRASTRUCTURE,
            pattern_type=AuditPatternType.NORMAL,
        )
        assert f.scope == AuditScope.INFRASTRUCTURE
        assert f.pattern_type == AuditPatternType.NORMAL
        assert f.severity_score == 0.5

    def test_with_params(self):
        eng = _engine()
        f = eng.record_finding(
            scope=AuditScope.SECURITY,
            pattern_type=AuditPatternType.PRIVILEGE_MISUSE,
            actor="admin-user",
            resource="iam-policy",
            description="Unauthorized policy change",
            severity_score=0.9,
        )
        assert f.scope == AuditScope.SECURITY
        assert f.pattern_type == AuditPatternType.PRIVILEGE_MISUSE
        assert f.actor == "admin-user"
        assert f.resource == "iam-policy"
        assert f.description == "Unauthorized policy change"
        assert f.severity_score == 0.9

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_finding(
                scope=AuditScope.INFRASTRUCTURE,
                pattern_type=AuditPatternType.NORMAL,
                actor=f"actor-{i}",
            )
        assert len(eng._findings) == 3


# ---------------------------------------------------------------------------
# get_finding
# ---------------------------------------------------------------------------


class TestGetFinding:
    def test_found(self):
        eng = _engine()
        f = eng.record_finding(
            scope=AuditScope.INFRASTRUCTURE,
            pattern_type=AuditPatternType.NORMAL,
            actor="actor-1",
        )
        result = eng.get_finding(f.id)
        assert result is not None
        assert result.actor == "actor-1"

    def test_not_found(self):
        eng = _engine()
        assert eng.get_finding("nonexistent") is None


# ---------------------------------------------------------------------------
# list_findings
# ---------------------------------------------------------------------------


class TestListFindings:
    def test_list_all(self):
        eng = _engine()
        eng.record_finding(scope=AuditScope.INFRASTRUCTURE, pattern_type=AuditPatternType.NORMAL)
        eng.record_finding(scope=AuditScope.SECURITY, pattern_type=AuditPatternType.BULK_CHANGE)
        assert len(eng.list_findings()) == 2

    def test_filter_by_scope(self):
        eng = _engine()
        eng.record_finding(scope=AuditScope.INFRASTRUCTURE, pattern_type=AuditPatternType.NORMAL)
        eng.record_finding(scope=AuditScope.SECURITY, pattern_type=AuditPatternType.BULK_CHANGE)
        results = eng.list_findings(scope=AuditScope.SECURITY)
        assert len(results) == 1
        assert results[0].scope == AuditScope.SECURITY

    def test_filter_by_pattern_type(self):
        eng = _engine()
        eng.record_finding(scope=AuditScope.INFRASTRUCTURE, pattern_type=AuditPatternType.NORMAL)
        eng.record_finding(scope=AuditScope.SECURITY, pattern_type=AuditPatternType.BULK_CHANGE)
        results = eng.list_findings(pattern_type=AuditPatternType.BULK_CHANGE)
        assert len(results) == 1
        assert results[0].pattern_type == AuditPatternType.BULK_CHANGE


# ---------------------------------------------------------------------------
# evaluate_completeness
# ---------------------------------------------------------------------------


class TestEvaluateCompleteness:
    def test_complete(self):
        eng = _engine()
        score = eng.evaluate_completeness(
            scope=AuditScope.INFRASTRUCTURE,
            total_expected_events=100,
            total_actual_events=98,
        )
        assert score.scope == AuditScope.INFRASTRUCTURE
        assert score.completeness_pct == 98.0
        assert score.completeness == CompletenessLevel.COMPLETE
        assert score.gap_count == 2

    def test_partial(self):
        eng = _engine()
        score = eng.evaluate_completeness(
            scope=AuditScope.DATABASE,
            total_expected_events=100,
            total_actual_events=65,
        )
        assert score.completeness_pct == 65.0
        assert score.completeness == CompletenessLevel.PARTIAL
        assert score.gap_count == 35

    def test_zero_expected(self):
        eng = _engine()
        score = eng.evaluate_completeness(
            scope=AuditScope.APPLICATION,
            total_expected_events=0,
            total_actual_events=0,
        )
        assert score.completeness_pct == 0.0
        assert score.completeness == CompletenessLevel.MISSING


# ---------------------------------------------------------------------------
# detect_gaps
# ---------------------------------------------------------------------------


class TestDetectGaps:
    def test_has_gaps(self):
        eng = _engine(min_completeness_pct=90.0)
        eng.evaluate_completeness(
            scope=AuditScope.INFRASTRUCTURE,
            total_expected_events=100,
            total_actual_events=70,
        )
        eng.evaluate_completeness(
            scope=AuditScope.SECURITY,
            total_expected_events=100,
            total_actual_events=98,
        )
        gaps = eng.detect_gaps()
        assert len(gaps) == 1
        assert gaps[0]["scope"] == "infrastructure"
        assert gaps[0]["completeness_pct"] == 70.0

    def test_no_gaps(self):
        eng = _engine(min_completeness_pct=90.0)
        eng.evaluate_completeness(
            scope=AuditScope.INFRASTRUCTURE,
            total_expected_events=100,
            total_actual_events=95,
        )
        gaps = eng.detect_gaps()
        assert gaps == []


# ---------------------------------------------------------------------------
# detect_suspicious_patterns
# ---------------------------------------------------------------------------


class TestDetectSuspiciousPatterns:
    def test_has_suspicious(self):
        eng = _engine()
        eng.record_finding(
            scope=AuditScope.SECURITY,
            pattern_type=AuditPatternType.SUSPICIOUS_MODIFICATION,
            actor="bad-actor",
        )
        eng.record_finding(
            scope=AuditScope.INFRASTRUCTURE,
            pattern_type=AuditPatternType.NORMAL,
            actor="good-actor",
        )
        results = eng.detect_suspicious_patterns()
        assert len(results) == 1
        assert results[0]["actor"] == "bad-actor"
        assert results[0]["pattern_type"] == "suspicious_modification"

    def test_no_suspicious(self):
        eng = _engine()
        eng.record_finding(
            scope=AuditScope.INFRASTRUCTURE,
            pattern_type=AuditPatternType.NORMAL,
        )
        results = eng.detect_suspicious_patterns()
        assert results == []


# ---------------------------------------------------------------------------
# score_audit_integrity
# ---------------------------------------------------------------------------


class TestScoreAuditIntegrity:
    def test_with_scores(self):
        eng = _engine()
        eng.evaluate_completeness(
            scope=AuditScope.INFRASTRUCTURE,
            total_expected_events=100,
            total_actual_events=95,
        )
        eng.record_finding(
            scope=AuditScope.SECURITY,
            pattern_type=AuditPatternType.SUSPICIOUS_MODIFICATION,
        )
        result = eng.score_audit_integrity()
        assert result["scopes_evaluated"] == 1
        assert result["completeness_avg_pct"] == 95.0
        assert result["suspicious_findings"] == 1
        assert result["penalty_applied"] == 2
        assert result["integrity_score"] == 93.0

    def test_no_scores(self):
        eng = _engine()
        result = eng.score_audit_integrity()
        assert result["integrity_score"] == 0.0
        assert result["scopes_evaluated"] == 0


# ---------------------------------------------------------------------------
# identify_actors_of_concern
# ---------------------------------------------------------------------------


class TestIdentifyActorsOfConcern:
    def test_has_actors(self):
        eng = _engine()
        eng.record_finding(
            scope=AuditScope.SECURITY,
            pattern_type=AuditPatternType.PRIVILEGE_MISUSE,
            actor="admin-1",
            severity_score=0.9,
        )
        eng.record_finding(
            scope=AuditScope.INFRASTRUCTURE,
            pattern_type=AuditPatternType.NORMAL,
            actor="good-user",
        )
        results = eng.identify_actors_of_concern()
        assert len(results) == 1
        assert results[0]["actor"] == "admin-1"
        assert results[0]["max_severity"] == 0.9
        assert results[0]["finding_count"] == 1

    def test_no_actors(self):
        eng = _engine()
        eng.record_finding(
            scope=AuditScope.INFRASTRUCTURE,
            pattern_type=AuditPatternType.NORMAL,
            actor="good-user",
        )
        results = eng.identify_actors_of_concern()
        assert results == []


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_finding(
            scope=AuditScope.SECURITY,
            pattern_type=AuditPatternType.SUSPICIOUS_MODIFICATION,
            actor="bad-actor",
            severity_score=0.8,
        )
        eng.record_finding(
            scope=AuditScope.INFRASTRUCTURE,
            pattern_type=AuditPatternType.NORMAL,
            actor="good-actor",
        )
        eng.evaluate_completeness(
            scope=AuditScope.INFRASTRUCTURE,
            total_expected_events=100,
            total_actual_events=70,
        )
        report = eng.generate_report()
        assert isinstance(report, AuditTrailReport)
        assert report.total_findings == 2
        assert report.suspicious_count == 1
        assert report.avg_completeness_pct == 70.0
        assert len(report.by_pattern_type) == 2
        assert len(report.by_scope) == 2
        assert len(report.actors_of_concern) >= 1
        assert len(report.recommendations) > 0
        assert report.generated_at > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_findings == 0
        assert report.suspicious_count == 0
        assert len(report.recommendations) > 0
        assert "Average completeness 0.0% below target 90.0%" in report.recommendations


# ---------------------------------------------------------------------------
# clear_data
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_finding(
            scope=AuditScope.INFRASTRUCTURE,
            pattern_type=AuditPatternType.NORMAL,
        )
        eng.evaluate_completeness(
            scope=AuditScope.INFRASTRUCTURE,
            total_expected_events=100,
            total_actual_events=95,
        )
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._findings) == 0
        assert len(eng._completeness_scores) == 0


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_findings"] == 0
        assert stats["total_completeness_scores"] == 0
        assert stats["pattern_distribution"] == {}
        assert stats["unique_actors"] == 0

    def test_populated(self):
        eng = _engine()
        eng.record_finding(
            scope=AuditScope.SECURITY,
            pattern_type=AuditPatternType.SUSPICIOUS_MODIFICATION,
            actor="admin-1",
        )
        eng.evaluate_completeness(
            scope=AuditScope.INFRASTRUCTURE,
            total_expected_events=100,
            total_actual_events=95,
        )
        stats = eng.get_stats()
        assert stats["total_findings"] == 1
        assert stats["total_completeness_scores"] == 1
        assert stats["min_completeness_pct"] == 90.0
        assert "suspicious_modification" in stats["pattern_distribution"]
        assert stats["unique_actors"] == 1
