"""Tests for Agent ROI Tracker (Phase 17 — F11)."""

from __future__ import annotations

import pytest

from shieldops.agents.roi_tracker import (
    AgentActionType,
    AgentROIReport,
    AgentROITracker,
    ImpactCategory,
    ROIEntry,
    ROISummary,
)

# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------


def _tracker(**kw) -> AgentROITracker:
    return AgentROITracker(**kw)


def _record(
    t: AgentROITracker,
    agent_id: str = "agent-001",
    agent_type: AgentActionType = AgentActionType.REMEDIATION,
    category: ImpactCategory = ImpactCategory.COST_SAVINGS,
    monetary_value: float = 100.0,
    time_saved_minutes: float = 30.0,
    **kw,
) -> ROIEntry:
    return t.record_impact(
        agent_id=agent_id,
        agent_type=agent_type,
        category=category,
        monetary_value=monetary_value,
        time_saved_minutes=time_saved_minutes,
        **kw,
    )


# -------------------------------------------------------------------
# Enum values
# -------------------------------------------------------------------


class TestEnums:
    def test_impact_cost_savings(self):
        assert ImpactCategory.COST_SAVINGS == "cost_savings"

    def test_impact_time_savings(self):
        assert ImpactCategory.TIME_SAVINGS == "time_savings"

    def test_impact_incident_prevention(self):
        assert ImpactCategory.INCIDENT_PREVENTION == "incident_prevention"

    def test_impact_security_fix(self):
        assert ImpactCategory.SECURITY_FIX == "security_fix"

    def test_impact_compliance(self):
        assert ImpactCategory.COMPLIANCE == "compliance"

    def test_action_investigation(self):
        assert AgentActionType.INVESTIGATION == "investigation"

    def test_action_remediation(self):
        assert AgentActionType.REMEDIATION == "remediation"

    def test_action_security_patch(self):
        assert AgentActionType.SECURITY_PATCH == "security_patch"

    def test_action_cost_optimization(self):
        assert AgentActionType.COST_OPTIMIZATION == "cost_optimization"

    def test_action_prediction(self):
        assert AgentActionType.PREDICTION == "prediction"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_roi_entry_defaults(self):
        e = ROIEntry(
            agent_id="a1",
            agent_type=AgentActionType.REMEDIATION,
            category=ImpactCategory.COST_SAVINGS,
        )
        assert e.id
        assert e.description == ""
        assert e.monetary_value == 0.0
        assert e.time_saved_minutes == 0.0
        assert e.currency == "USD"
        assert e.metadata == {}
        assert e.recorded_at > 0

    def test_roi_entry_full(self):
        e = ROIEntry(
            agent_id="a1",
            agent_type=AgentActionType.SECURITY_PATCH,
            category=ImpactCategory.SECURITY_FIX,
            description="Patched CVE-2024-1234",
            monetary_value=5000.0,
            time_saved_minutes=120.0,
            currency="EUR",
            metadata={"cve": "CVE-2024-1234"},
        )
        assert e.monetary_value == 5000.0
        assert e.currency == "EUR"
        assert e.metadata["cve"] == "CVE-2024-1234"

    def test_agent_roi_report_defaults(self):
        r = AgentROIReport(agent_type="remediation")
        assert r.total_entries == 0
        assert r.total_monetary_value == 0.0
        assert r.total_time_saved_minutes == 0.0
        assert r.top_category == ""
        assert r.currency == "USD"

    def test_roi_summary_defaults(self):
        s = ROISummary()
        assert s.total_value == 0.0
        assert s.total_time_saved_hours == 0.0
        assert s.by_agent_type == {}
        assert s.by_category == {}
        assert s.period == ""


# -------------------------------------------------------------------
# record_impact
# -------------------------------------------------------------------


class TestRecordImpact:
    def test_basic_record(self):
        t = _tracker()
        e = _record(t)
        assert e.agent_id == "agent-001"
        assert e.monetary_value == 100.0

    def test_record_all_fields(self):
        t = _tracker()
        e = t.record_impact(
            agent_id="agent-002",
            agent_type=AgentActionType.INVESTIGATION,
            category=ImpactCategory.INCIDENT_PREVENTION,
            description="Prevented outage",
            monetary_value=25000.0,
            time_saved_minutes=480.0,
            currency="GBP",
            metadata={"severity": "P1"},
        )
        assert e.description == "Prevented outage"
        assert e.currency == "GBP"
        assert e.metadata["severity"] == "P1"

    def test_unique_ids(self):
        t = _tracker()
        e1 = _record(t, agent_id="a1")
        e2 = _record(t, agent_id="a2")
        assert e1.id != e2.id

    def test_max_entries_limit(self):
        t = _tracker(max_entries=2)
        _record(t, agent_id="a1")
        _record(t, agent_id="a2")
        with pytest.raises(ValueError, match="Maximum entries limit"):
            _record(t, agent_id="a3")


# -------------------------------------------------------------------
# get_agent_report
# -------------------------------------------------------------------


class TestGetAgentReport:
    def test_empty_report(self):
        t = _tracker()
        r = t.get_agent_report(AgentActionType.REMEDIATION)
        assert r.total_entries == 0
        assert r.total_monetary_value == 0.0

    def test_single_type(self):
        t = _tracker()
        _record(t, monetary_value=100.0, time_saved_minutes=30.0)
        _record(t, monetary_value=200.0, time_saved_minutes=60.0)
        r = t.get_agent_report(AgentActionType.REMEDIATION)
        assert r.total_entries == 2
        assert r.total_monetary_value == pytest.approx(300.0)
        assert r.total_time_saved_minutes == pytest.approx(90.0)

    def test_filters_by_type(self):
        t = _tracker()
        _record(
            t,
            agent_type=AgentActionType.REMEDIATION,
            monetary_value=100.0,
        )
        _record(
            t,
            agent_type=AgentActionType.INVESTIGATION,
            monetary_value=50.0,
        )
        r = t.get_agent_report(AgentActionType.REMEDIATION)
        assert r.total_entries == 1
        assert r.total_monetary_value == pytest.approx(100.0)

    def test_top_category(self):
        t = _tracker()
        _record(
            t,
            category=ImpactCategory.COST_SAVINGS,
            monetary_value=500.0,
        )
        _record(
            t,
            category=ImpactCategory.TIME_SAVINGS,
            monetary_value=100.0,
        )
        r = t.get_agent_report(AgentActionType.REMEDIATION)
        assert r.top_category == ImpactCategory.COST_SAVINGS


# -------------------------------------------------------------------
# get_summary
# -------------------------------------------------------------------


class TestGetSummary:
    def test_empty_summary(self):
        t = _tracker()
        s = t.get_summary()
        assert s.total_value == 0.0
        assert s.total_time_saved_hours == 0.0

    def test_summary_totals(self):
        t = _tracker()
        _record(t, monetary_value=600.0, time_saved_minutes=120.0)
        _record(t, monetary_value=400.0, time_saved_minutes=60.0)
        s = t.get_summary()
        assert s.total_value == pytest.approx(1000.0)
        assert s.total_time_saved_hours == pytest.approx(3.0)

    def test_summary_by_agent_type(self):
        t = _tracker()
        _record(
            t,
            agent_type=AgentActionType.REMEDIATION,
            monetary_value=100.0,
        )
        _record(
            t,
            agent_type=AgentActionType.INVESTIGATION,
            monetary_value=50.0,
        )
        s = t.get_summary()
        assert s.by_agent_type["remediation"] == pytest.approx(100.0)
        assert s.by_agent_type["investigation"] == pytest.approx(50.0)

    def test_summary_by_category(self):
        t = _tracker()
        _record(
            t,
            category=ImpactCategory.COST_SAVINGS,
            monetary_value=200.0,
        )
        _record(
            t,
            category=ImpactCategory.SECURITY_FIX,
            monetary_value=300.0,
        )
        s = t.get_summary()
        assert s.by_category["cost_savings"] == pytest.approx(200.0)
        assert s.by_category["security_fix"] == pytest.approx(300.0)

    def test_summary_period(self):
        t = _tracker()
        s = t.get_summary(period="2025-Q4")
        assert s.period == "2025-Q4"


# -------------------------------------------------------------------
# get_top_agents
# -------------------------------------------------------------------


class TestGetTopAgents:
    def test_empty(self):
        t = _tracker()
        assert t.get_top_agents() == []

    def test_ranking_order(self):
        t = _tracker()
        _record(t, agent_id="low", monetary_value=10.0)
        _record(t, agent_id="high", monetary_value=500.0)
        _record(t, agent_id="mid", monetary_value=100.0)
        top = t.get_top_agents()
        assert top[0]["agent_id"] == "high"
        assert top[1]["agent_id"] == "mid"
        assert top[2]["agent_id"] == "low"

    def test_limit_applied(self):
        t = _tracker()
        for i in range(5):
            _record(t, agent_id=f"agent-{i}", monetary_value=float(i))
        assert len(t.get_top_agents(limit=3)) == 3

    def test_aggregation_per_agent(self):
        t = _tracker()
        _record(t, agent_id="a1", monetary_value=100.0)
        _record(t, agent_id="a1", monetary_value=200.0)
        top = t.get_top_agents()
        assert len(top) == 1
        assert top[0]["total_value"] == pytest.approx(300.0)
        assert top[0]["entry_count"] == 2


# -------------------------------------------------------------------
# list_entries
# -------------------------------------------------------------------


class TestListEntries:
    def test_list_all(self):
        t = _tracker()
        _record(t, agent_id="a1")
        _record(t, agent_id="a2")
        assert len(t.list_entries()) == 2

    def test_filter_by_agent_type(self):
        t = _tracker()
        _record(t, agent_type=AgentActionType.REMEDIATION)
        _record(t, agent_type=AgentActionType.INVESTIGATION)
        rems = t.list_entries(agent_type=AgentActionType.REMEDIATION)
        assert len(rems) == 1

    def test_filter_by_category(self):
        t = _tracker()
        _record(t, category=ImpactCategory.COST_SAVINGS)
        _record(t, category=ImpactCategory.SECURITY_FIX)
        costs = t.list_entries(category=ImpactCategory.COST_SAVINGS)
        assert len(costs) == 1

    def test_limit_returns_tail(self):
        t = _tracker()
        for i in range(5):
            _record(t, agent_id=f"agent-{i}")
        entries = t.list_entries(limit=2)
        assert len(entries) == 2
        assert entries[0].agent_id == "agent-3"
        assert entries[1].agent_id == "agent-4"

    def test_list_empty(self):
        t = _tracker()
        assert t.list_entries() == []


# -------------------------------------------------------------------
# get_category_breakdown
# -------------------------------------------------------------------


class TestCategoryBreakdown:
    def test_empty(self):
        t = _tracker()
        assert t.get_category_breakdown() == {}

    def test_single_category(self):
        t = _tracker()
        _record(t, category=ImpactCategory.COST_SAVINGS, monetary_value=100.0)
        _record(t, category=ImpactCategory.COST_SAVINGS, monetary_value=200.0)
        bd = t.get_category_breakdown()
        assert bd["cost_savings"] == pytest.approx(300.0)

    def test_multiple_categories(self):
        t = _tracker()
        _record(t, category=ImpactCategory.COST_SAVINGS, monetary_value=100.0)
        _record(t, category=ImpactCategory.SECURITY_FIX, monetary_value=50.0)
        bd = t.get_category_breakdown()
        assert len(bd) == 2


# -------------------------------------------------------------------
# get_time_series
# -------------------------------------------------------------------


class TestTimeSeries:
    def test_empty(self):
        t = _tracker()
        assert t.get_time_series() == []

    def test_single_bucket(self):
        t = _tracker()
        _record(t, monetary_value=100.0, time_saved_minutes=30.0)
        ts = t.get_time_series(bucket_hours=24)
        assert len(ts) >= 1
        total_val = sum(b["total_value"] for b in ts)
        assert total_val == pytest.approx(100.0)

    def test_bucket_structure(self):
        t = _tracker()
        _record(t)
        ts = t.get_time_series()
        bucket = ts[0]
        assert "bucket_start" in bucket
        assert "bucket_end" in bucket
        assert "total_value" in bucket
        assert "total_time_saved_minutes" in bucket
        assert "entry_count" in bucket

    def test_entries_counted(self):
        t = _tracker()
        _record(t, monetary_value=10.0)
        _record(t, monetary_value=20.0)
        ts = t.get_time_series(bucket_hours=24)
        total_entries = sum(b["entry_count"] for b in ts)
        assert total_entries == 2


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty_stats(self):
        t = _tracker()
        s = t.get_stats()
        assert s["total_entries"] == 0
        assert s["total_monetary_value"] == 0.0
        assert s["total_time_saved_minutes"] == 0.0
        assert s["unique_agents"] == 0
        assert s["agent_types"] == []
        assert s["categories"] == []

    def test_populated_stats(self):
        t = _tracker()
        _record(
            t,
            agent_id="a1",
            agent_type=AgentActionType.REMEDIATION,
            category=ImpactCategory.COST_SAVINGS,
            monetary_value=100.0,
            time_saved_minutes=60.0,
        )
        _record(
            t,
            agent_id="a2",
            agent_type=AgentActionType.INVESTIGATION,
            category=ImpactCategory.SECURITY_FIX,
            monetary_value=200.0,
            time_saved_minutes=30.0,
        )
        s = t.get_stats()
        assert s["total_entries"] == 2
        assert s["total_monetary_value"] == pytest.approx(300.0)
        assert s["total_time_saved_minutes"] == pytest.approx(90.0)
        assert s["unique_agents"] == 2
        assert len(s["agent_types"]) == 2
        assert len(s["categories"]) == 2

    def test_unique_agents_deduped(self):
        t = _tracker()
        _record(t, agent_id="a1")
        _record(t, agent_id="a1")
        s = t.get_stats()
        assert s["unique_agents"] == 1
