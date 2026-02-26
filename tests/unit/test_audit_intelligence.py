"""Tests for shieldops.audit.audit_intelligence — AuditIntelligenceAnalyzer."""

from __future__ import annotations

from shieldops.audit.audit_intelligence import (
    AuditAnomaly,
    AuditCategory,
    AuditFinding,
    AuditIntelligenceAnalyzer,
    AuditIntelligenceReport,
    AuditPattern,
    AuditRiskLevel,
)


def _engine(**kw) -> AuditIntelligenceAnalyzer:
    return AuditIntelligenceAnalyzer(**kw)


class TestEnums:
    def test_cat_access(self):
        assert AuditCategory.ACCESS == "access"

    def test_cat_change(self):
        assert AuditCategory.CHANGE == "change"

    def test_cat_compliance(self):
        assert AuditCategory.COMPLIANCE == "compliance"

    def test_cat_security(self):
        assert AuditCategory.SECURITY == "security"

    def test_cat_financial(self):
        assert AuditCategory.FINANCIAL == "financial"

    def test_risk_critical(self):
        assert AuditRiskLevel.CRITICAL == "critical"

    def test_risk_high(self):
        assert AuditRiskLevel.HIGH == "high"

    def test_risk_medium(self):
        assert AuditRiskLevel.MEDIUM == "medium"

    def test_risk_low(self):
        assert AuditRiskLevel.LOW == "low"

    def test_risk_informational(self):
        assert AuditRiskLevel.INFORMATIONAL == "informational"

    def test_pattern_normal(self):
        assert AuditPattern.NORMAL == "normal"

    def test_pattern_unusual_timing(self):
        assert AuditPattern.UNUSUAL_TIMING == "unusual_timing"

    def test_pattern_privilege_escalation(self):
        assert AuditPattern.PRIVILEGE_ESCALATION == "privilege_escalation"

    def test_pattern_bulk_operation(self):
        assert AuditPattern.BULK_OPERATION == "bulk_operation"

    def test_pattern_policy_bypass(self):
        assert AuditPattern.POLICY_BYPASS == "policy_bypass"


class TestModels:
    def test_audit_finding_defaults(self):
        r = AuditFinding()
        assert r.id
        assert r.finding_name == ""
        assert r.category == AuditCategory.COMPLIANCE
        assert r.risk_level == AuditRiskLevel.MEDIUM
        assert r.pattern == AuditPattern.NORMAL
        assert r.affected_resource == ""
        assert r.deviation_pct == 0.0
        assert r.details == ""
        assert r.created_at > 0

    def test_audit_anomaly_defaults(self):
        r = AuditAnomaly()
        assert r.id
        assert r.anomaly_name == ""
        assert r.category == AuditCategory.COMPLIANCE
        assert r.risk_level == AuditRiskLevel.MEDIUM
        assert r.pattern == AuditPattern.UNUSUAL_TIMING
        assert r.baseline_value == 0.0
        assert r.observed_value == 0.0
        assert r.created_at > 0

    def test_audit_intelligence_report_defaults(self):
        r = AuditIntelligenceReport()
        assert r.total_findings == 0
        assert r.total_anomalies == 0
        assert r.avg_deviation_pct == 0.0
        assert r.by_category == {}
        assert r.by_risk_level == {}
        assert r.high_risk_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


class TestRecordFinding:
    def test_basic(self):
        eng = _engine()
        r = eng.record_finding("f1", deviation_pct=600.0)
        assert r.finding_name == "f1"
        assert r.risk_level == AuditRiskLevel.CRITICAL

    def test_auto_risk_high(self):
        eng = _engine()
        r = eng.record_finding("f2", deviation_pct=350.0)
        assert r.risk_level == AuditRiskLevel.HIGH

    def test_auto_risk_low(self):
        eng = _engine()
        r = eng.record_finding("f3", deviation_pct=60.0)
        assert r.risk_level == AuditRiskLevel.LOW

    def test_explicit_risk(self):
        eng = _engine()
        r = eng.record_finding("f4", risk_level=AuditRiskLevel.INFORMATIONAL)
        assert r.risk_level == AuditRiskLevel.INFORMATIONAL

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_finding(f"f-{i}")
        assert len(eng._records) == 3


class TestGetFinding:
    def test_found(self):
        eng = _engine()
        r = eng.record_finding("f1")
        assert eng.get_finding(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_finding("nonexistent") is None


class TestListFindings:
    def test_list_all(self):
        eng = _engine()
        eng.record_finding("f1")
        eng.record_finding("f2")
        assert len(eng.list_findings()) == 2

    def test_filter_by_category(self):
        eng = _engine()
        eng.record_finding("f1", category=AuditCategory.ACCESS)
        eng.record_finding("f2", category=AuditCategory.SECURITY)
        results = eng.list_findings(category=AuditCategory.ACCESS)
        assert len(results) == 1

    def test_filter_by_risk(self):
        eng = _engine()
        eng.record_finding("f1", risk_level=AuditRiskLevel.CRITICAL)
        eng.record_finding("f2", risk_level=AuditRiskLevel.LOW)
        results = eng.list_findings(risk_level=AuditRiskLevel.CRITICAL)
        assert len(results) == 1


class TestRecordAnomaly:
    def test_basic(self):
        eng = _engine()
        a = eng.record_anomaly(
            "a1",
            baseline_value=100.0,
            observed_value=500.0,
        )
        assert a.anomaly_name == "a1"
        assert a.baseline_value == 100.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.record_anomaly(f"a-{i}")
        assert len(eng._anomalies) == 2


class TestAnalyzeAuditPatterns:
    def test_with_data(self):
        eng = _engine()
        eng.record_finding("f1", category=AuditCategory.ACCESS, deviation_pct=100.0)
        result = eng.analyze_audit_patterns("access")
        assert result["category"] == "access"
        assert result["total_findings"] == 1

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_audit_patterns("ghost")
        assert result["status"] == "no_data"


class TestIdentifyHighRiskFindings:
    def test_with_high(self):
        eng = _engine()
        eng.record_finding("f1", deviation_pct=600.0)
        eng.record_finding("f2", deviation_pct=10.0)
        results = eng.identify_high_risk_findings()
        assert len(results) == 1

    def test_empty(self):
        eng = _engine()
        assert eng.identify_high_risk_findings() == []


class TestRankByAnomalyDeviation:
    def test_with_data(self):
        eng = _engine()
        eng.record_anomaly("a1", baseline_value=100.0, observed_value=500.0)
        eng.record_anomaly("a2", baseline_value=100.0, observed_value=150.0)
        results = eng.rank_by_anomaly_deviation()
        assert results[0]["anomaly_name"] == "a1"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_anomaly_deviation() == []


class TestDetectSuspiciousPatterns:
    def test_with_suspicious(self):
        eng = _engine()
        eng.record_finding("f1", pattern=AuditPattern.PRIVILEGE_ESCALATION)
        eng.record_finding("f2", pattern=AuditPattern.NORMAL)
        results = eng.detect_suspicious_patterns()
        assert len(results) == 1

    def test_empty(self):
        eng = _engine()
        assert eng.detect_suspicious_patterns() == []


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine()
        eng.record_finding("f1", deviation_pct=600.0)
        eng.record_finding("f2", pattern=AuditPattern.BULK_OPERATION)
        eng.record_anomaly("a1")
        report = eng.generate_report()
        assert report.total_findings == 2
        assert report.total_anomalies == 1
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_findings == 0
        assert "normal" in report.recommendations[0]


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_finding("f1")
        eng.record_anomaly("a1")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._anomalies) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_findings"] == 0
        assert stats["total_anomalies"] == 0
        assert stats["category_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_finding("f1", category=AuditCategory.ACCESS, affected_resource="res-a")
        eng.record_finding("f2", category=AuditCategory.SECURITY, affected_resource="res-b")
        eng.record_anomaly("a1")
        stats = eng.get_stats()
        assert stats["total_findings"] == 2
        assert stats["total_anomalies"] == 1
        assert stats["unique_resources"] == 2
