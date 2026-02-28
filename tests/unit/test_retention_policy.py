"""Tests for shieldops.observability.retention_policy — DataRetentionPolicyManager."""

from __future__ import annotations

from shieldops.observability.retention_policy import (
    ComplianceRequirement,
    DataCategory,
    DataRetentionPolicyManager,
    RetentionPolicyReport,
    RetentionRecord,
    RetentionRule,
    RetentionTier,
)


def _engine(**kw) -> DataRetentionPolicyManager:
    return DataRetentionPolicyManager(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # DataCategory (5)
    def test_category_metrics(self):
        assert DataCategory.METRICS == "metrics"

    def test_category_logs(self):
        assert DataCategory.LOGS == "logs"

    def test_category_traces(self):
        assert DataCategory.TRACES == "traces"

    def test_category_events(self):
        assert DataCategory.EVENTS == "events"

    def test_category_backups(self):
        assert DataCategory.BACKUPS == "backups"

    # RetentionTier (5)
    def test_tier_hot(self):
        assert RetentionTier.HOT == "hot"

    def test_tier_warm(self):
        assert RetentionTier.WARM == "warm"

    def test_tier_cold(self):
        assert RetentionTier.COLD == "cold"

    def test_tier_archive(self):
        assert RetentionTier.ARCHIVE == "archive"

    def test_tier_deleted(self):
        assert RetentionTier.DELETED == "deleted"

    # ComplianceRequirement (5)
    def test_compliance_soc2(self):
        assert ComplianceRequirement.SOC2 == "soc2"

    def test_compliance_hipaa(self):
        assert ComplianceRequirement.HIPAA == "hipaa"

    def test_compliance_gdpr(self):
        assert ComplianceRequirement.GDPR == "gdpr"

    def test_compliance_pci_dss(self):
        assert ComplianceRequirement.PCI_DSS == "pci_dss"

    def test_compliance_internal(self):
        assert ComplianceRequirement.INTERNAL == "internal"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_retention_record_defaults(self):
        r = RetentionRecord()
        assert r.id
        assert r.service_name == ""
        assert r.data_category == DataCategory.METRICS
        assert r.tier == RetentionTier.HOT
        assert r.compliance == ComplianceRequirement.INTERNAL
        assert r.retention_days == 0
        assert r.details == ""
        assert r.created_at > 0

    def test_retention_rule_defaults(self):
        r = RetentionRule()
        assert r.id
        assert r.rule_name == ""
        assert r.data_category == DataCategory.METRICS
        assert r.tier == RetentionTier.HOT
        assert r.max_days == 365
        assert r.description == ""
        assert r.created_at > 0

    def test_report_defaults(self):
        r = RetentionPolicyReport()
        assert r.total_records == 0
        assert r.total_rules == 0
        assert r.avg_retention_days == 0.0
        assert r.by_category == {}
        assert r.by_tier == {}
        assert r.violation_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_retention
# -------------------------------------------------------------------


class TestRecordRetention:
    def test_basic(self):
        eng = _engine()
        r = eng.record_retention(
            "svc-a",
            data_category=DataCategory.LOGS,
            tier=RetentionTier.WARM,
        )
        assert r.service_name == "svc-a"
        assert r.data_category == DataCategory.LOGS

    def test_with_compliance(self):
        eng = _engine()
        r = eng.record_retention(
            "svc-b",
            compliance=ComplianceRequirement.HIPAA,
            retention_days=730,
        )
        assert r.compliance == ComplianceRequirement.HIPAA
        assert r.retention_days == 730

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_retention(f"svc-{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_retention
# -------------------------------------------------------------------


class TestGetRetention:
    def test_found(self):
        eng = _engine()
        r = eng.record_retention("svc-a")
        assert eng.get_retention(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_retention("nonexistent") is None


# -------------------------------------------------------------------
# list_retentions
# -------------------------------------------------------------------


class TestListRetentions:
    def test_list_all(self):
        eng = _engine()
        eng.record_retention("svc-a")
        eng.record_retention("svc-b")
        assert len(eng.list_retentions()) == 2

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_retention("svc-a")
        eng.record_retention("svc-b")
        results = eng.list_retentions(service_name="svc-a")
        assert len(results) == 1

    def test_filter_by_category(self):
        eng = _engine()
        eng.record_retention("svc-a", data_category=DataCategory.TRACES)
        eng.record_retention("svc-b", data_category=DataCategory.METRICS)
        results = eng.list_retentions(data_category=DataCategory.TRACES)
        assert len(results) == 1


# -------------------------------------------------------------------
# add_rule
# -------------------------------------------------------------------


class TestAddRule:
    def test_basic(self):
        eng = _engine()
        r = eng.add_rule(
            "rule-1",
            data_category=DataCategory.LOGS,
            tier=RetentionTier.COLD,
            max_days=180,
        )
        assert r.rule_name == "rule-1"
        assert r.max_days == 180

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_rule(f"rule-{i}")
        assert len(eng._rules) == 2


# -------------------------------------------------------------------
# analyze_retention_compliance
# -------------------------------------------------------------------


class TestAnalyzeRetentionCompliance:
    def test_with_data(self):
        eng = _engine()
        eng.record_retention("svc-a", retention_days=200)
        eng.record_retention("svc-a", retention_days=400)
        result = eng.analyze_retention_compliance("svc-a")
        assert result["service_name"] == "svc-a"
        assert result["total_records"] == 2
        assert result["avg_retention_days"] == 300.0

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_retention_compliance("ghost")
        assert result["status"] == "no_data"

    def test_meets_threshold(self):
        eng = _engine(max_retention_days=365)
        eng.record_retention("svc-a", retention_days=200)
        result = eng.analyze_retention_compliance("svc-a")
        assert result["meets_threshold"] is True


# -------------------------------------------------------------------
# identify_retention_violations
# -------------------------------------------------------------------


class TestIdentifyRetentionViolations:
    def test_with_violations(self):
        eng = _engine(max_retention_days=365)
        eng.record_retention("svc-a", retention_days=400)
        eng.record_retention("svc-a", retention_days=500)
        eng.record_retention("svc-b", retention_days=100)
        results = eng.identify_retention_violations()
        assert len(results) == 1
        assert results[0]["service_name"] == "svc-a"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_retention_violations() == []


# -------------------------------------------------------------------
# rank_by_retention_days
# -------------------------------------------------------------------


class TestRankByRetentionDays:
    def test_with_data(self):
        eng = _engine()
        eng.record_retention("svc-a", retention_days=500)
        eng.record_retention("svc-a", retention_days=300)
        eng.record_retention("svc-b", retention_days=100)
        results = eng.rank_by_retention_days()
        assert results[0]["service_name"] == "svc-a"
        assert results[0]["avg_retention_days"] == 400.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_retention_days() == []


# -------------------------------------------------------------------
# detect_retention_trends
# -------------------------------------------------------------------


class TestDetectRetentionTrends:
    def test_with_recurring(self):
        eng = _engine()
        for _ in range(5):
            eng.record_retention("svc-a")
        eng.record_retention("svc-b")
        results = eng.detect_retention_trends()
        assert len(results) == 1
        assert results[0]["service_name"] == "svc-a"
        assert results[0]["recurring"] is True

    def test_no_recurring(self):
        eng = _engine()
        eng.record_retention("svc-a")
        assert eng.detect_retention_trends() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine()
        eng.record_retention("svc-a", retention_days=200, tier=RetentionTier.HOT)
        eng.record_retention("svc-b", retention_days=100, tier=RetentionTier.COLD)
        eng.add_rule("rule-1")
        report = eng.generate_report()
        assert report.total_records == 2
        assert report.total_rules == 1
        assert report.by_category != {}
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert report.recommendations[0] == "Data retention policy management meets targets"

    def test_exceeds_limit(self):
        eng = _engine(max_retention_days=100)
        eng.record_retention("svc-a", retention_days=500)
        report = eng.generate_report()
        assert "exceeds" in report.recommendations[0]


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_retention("svc-a")
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
        assert stats["total_records"] == 0
        assert stats["total_rules"] == 0
        assert stats["category_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_retention("svc-a", data_category=DataCategory.METRICS)
        eng.record_retention("svc-b", data_category=DataCategory.LOGS)
        eng.add_rule("r1")
        stats = eng.get_stats()
        assert stats["total_records"] == 2
        assert stats["total_rules"] == 1
        assert stats["unique_services"] == 2
