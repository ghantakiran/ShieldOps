"""Tests for SecurityDebtQuantifier."""

from __future__ import annotations

from shieldops.security.security_debt_quantifier import (
    DebtCategory,
    DebtPriority,
    RemediationEffort,
    SecurityDebtQuantifier,
)


def _engine(**kw) -> SecurityDebtQuantifier:
    return SecurityDebtQuantifier(**kw)


class TestEnums:
    def test_cat_vuln(self):
        assert DebtCategory.VULNERABILITY == "vulnerability"

    def test_cat_config(self):
        assert DebtCategory.CONFIGURATION == "configuration"

    def test_cat_process(self):
        assert DebtCategory.PROCESS == "process"

    def test_cat_arch(self):
        assert DebtCategory.ARCHITECTURE == "architecture"

    def test_pri_critical(self):
        assert DebtPriority.CRITICAL == "critical"

    def test_pri_high(self):
        assert DebtPriority.HIGH == "high"

    def test_pri_medium(self):
        assert DebtPriority.MEDIUM == "medium"

    def test_pri_low(self):
        assert DebtPriority.LOW == "low"

    def test_effort_trivial(self):
        assert RemediationEffort.TRIVIAL == "trivial"

    def test_effort_minor(self):
        assert RemediationEffort.MINOR == "minor"

    def test_effort_moderate(self):
        assert RemediationEffort.MODERATE == "moderate"

    def test_effort_major(self):
        assert RemediationEffort.MAJOR == "major"


class TestAddRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.add_record(
            debt_id="d1",
            category=DebtCategory.VULNERABILITY,
            debt_score=90.0,
        )
        assert r.debt_id == "d1"

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.add_record(debt_id=f"d-{i}")
        assert len(eng._records) == 3


class TestProcess:
    def test_returns_analysis(self):
        eng = _engine()
        r = eng.add_record(
            debt_id="d1",
            debt_score=100.0,
            age_days=60,
        )
        a = eng.process(r.id)
        assert a is not None
        assert a.debt_id == "d1"
        assert a.compounded_debt > 100.0

    def test_missing_key(self):
        assert _engine().process("x") is None


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.add_record(debt_id="d1")
        assert eng.generate_report().total_records == 1

    def test_empty(self):
        assert _engine().generate_report().total_records == 0


class TestGetStats:
    def test_has_total_records(self):
        assert "total_records" in _engine().get_stats()

    def test_populated(self):
        eng = _engine()
        eng.add_record(debt_id="d1")
        assert eng.get_stats()["total_records"] == 1


class TestClearData:
    def test_resets(self):
        eng = _engine()
        eng.add_record(debt_id="d1")
        eng.clear_data()
        assert len(eng._records) == 0


class TestQuantifySecurityDebt:
    def test_basic(self):
        eng = _engine()
        eng.add_record(
            debt_id="d1",
            category=DebtCategory.PROCESS,
            debt_score=50.0,
        )
        result = eng.quantify_security_debt()
        assert len(result) == 1
        assert result[0]["category"] == "process"

    def test_empty(self):
        assert _engine().quantify_security_debt() == []


class TestComputeDebtInterestRate:
    def test_basic(self):
        eng = _engine()
        eng.add_record(debt_id="d1", age_days=90)
        result = eng.compute_debt_interest_rate()
        assert result["avg_interest_rate"] > 0

    def test_empty(self):
        result = _engine().compute_debt_interest_rate()
        assert result["avg_interest_rate"] == 0.0


class TestPrioritizeDebtReduction:
    def test_basic(self):
        eng = _engine()
        eng.add_record(
            debt_id="d1",
            debt_score=100.0,
            effort=RemediationEffort.TRIVIAL,
        )
        eng.add_record(
            debt_id="d2",
            debt_score=100.0,
            effort=RemediationEffort.MAJOR,
        )
        result = eng.prioritize_debt_reduction()
        assert result[0]["debt_id"] == "d1"

    def test_empty(self):
        assert _engine().prioritize_debt_reduction() == []
