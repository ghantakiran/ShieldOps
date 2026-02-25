"""Tests for shieldops.compliance.evidence_scheduler — ComplianceEvidenceScheduler."""

from __future__ import annotations

import time

from shieldops.compliance.evidence_scheduler import (
    CollectionFrequency,
    CollectionTask,
    ComplianceEvidenceScheduler,
    ComplianceFramework,
    EvidenceSchedule,
    SchedulerReport,
    ScheduleStatus,
)


def _engine(**kw) -> ComplianceEvidenceScheduler:
    return ComplianceEvidenceScheduler(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    # CollectionFrequency (5)
    def test_frequency_daily(self):
        assert CollectionFrequency.DAILY == "daily"

    def test_frequency_weekly(self):
        assert CollectionFrequency.WEEKLY == "weekly"

    def test_frequency_monthly(self):
        assert CollectionFrequency.MONTHLY == "monthly"

    def test_frequency_quarterly(self):
        assert CollectionFrequency.QUARTERLY == "quarterly"

    def test_frequency_annual(self):
        assert CollectionFrequency.ANNUAL == "annual"

    # ScheduleStatus (5)
    def test_status_on_time(self):
        assert ScheduleStatus.ON_TIME == "on_time"

    def test_status_upcoming(self):
        assert ScheduleStatus.UPCOMING == "upcoming"

    def test_status_due_soon(self):
        assert ScheduleStatus.DUE_SOON == "due_soon"

    def test_status_overdue(self):
        assert ScheduleStatus.OVERDUE == "overdue"

    def test_status_missed(self):
        assert ScheduleStatus.MISSED == "missed"

    # ComplianceFramework (5)
    def test_framework_soc2(self):
        assert ComplianceFramework.SOC2 == "soc2"

    def test_framework_hipaa(self):
        assert ComplianceFramework.HIPAA == "hipaa"

    def test_framework_pci_dss(self):
        assert ComplianceFramework.PCI_DSS == "pci_dss"

    def test_framework_gdpr(self):
        assert ComplianceFramework.GDPR == "gdpr"

    def test_framework_iso_27001(self):
        assert ComplianceFramework.ISO_27001 == "iso_27001"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_evidence_schedule_defaults(self):
        s = EvidenceSchedule()
        assert s.id
        assert s.evidence_name == ""
        assert s.framework == ComplianceFramework.SOC2
        assert s.frequency == CollectionFrequency.MONTHLY
        assert s.status == ScheduleStatus.ON_TIME
        assert s.next_due_at == 0.0
        assert s.last_collected_at == 0.0
        assert s.owner == ""
        assert s.description == ""
        assert s.created_at > 0

    def test_collection_task_defaults(self):
        t = CollectionTask()
        assert t.id
        assert t.schedule_id == ""
        assert t.evidence_name == ""
        assert t.status == "pending"
        assert t.due_at == 0.0
        assert t.completed_at == 0.0
        assert t.collected_by == ""
        assert t.created_at > 0

    def test_scheduler_report_defaults(self):
        r = SchedulerReport()
        assert r.total_schedules == 0
        assert r.total_tasks == 0
        assert r.total_overdue == 0
        assert r.total_completed == 0
        assert r.by_framework == {}
        assert r.by_frequency == {}
        assert r.by_status == {}
        assert r.overdue_schedules == []
        assert r.recommendations == []
        assert r.generated_at > 0


# ---------------------------------------------------------------------------
# create_schedule
# ---------------------------------------------------------------------------


class TestCreateSchedule:
    def test_basic_creation(self):
        eng = _engine()
        s = eng.create_schedule(
            evidence_name="access-review",
            framework=ComplianceFramework.SOC2,
            frequency=CollectionFrequency.QUARTERLY,
            owner="compliance-team",
        )
        assert s.evidence_name == "access-review"
        assert s.framework == ComplianceFramework.SOC2
        assert s.frequency == CollectionFrequency.QUARTERLY
        assert s.owner == "compliance-team"
        assert s.status == ScheduleStatus.ON_TIME

    def test_with_due_date(self):
        eng = _engine()
        future = time.time() + 86400 * 30
        s = eng.create_schedule(
            evidence_name="audit-log",
            next_due_at=future,
        )
        assert s.next_due_at == future

    def test_eviction_at_max(self):
        eng = _engine(max_schedules=3)
        for i in range(5):
            eng.create_schedule(evidence_name=f"evidence-{i}")
        assert len(eng._schedules) == 3


# ---------------------------------------------------------------------------
# get_schedule
# ---------------------------------------------------------------------------


class TestGetSchedule:
    def test_found(self):
        eng = _engine()
        s = eng.create_schedule(evidence_name="access-review")
        result = eng.get_schedule(s.id)
        assert result is not None
        assert result.evidence_name == "access-review"

    def test_not_found(self):
        eng = _engine()
        assert eng.get_schedule("nonexistent") is None


# ---------------------------------------------------------------------------
# list_schedules
# ---------------------------------------------------------------------------


class TestListSchedules:
    def test_list_all(self):
        eng = _engine()
        eng.create_schedule(evidence_name="access-review")
        eng.create_schedule(evidence_name="audit-log")
        assert len(eng.list_schedules()) == 2

    def test_filter_by_framework(self):
        eng = _engine()
        eng.create_schedule(
            evidence_name="access-review",
            framework=ComplianceFramework.SOC2,
        )
        eng.create_schedule(
            evidence_name="data-map",
            framework=ComplianceFramework.GDPR,
        )
        results = eng.list_schedules(framework=ComplianceFramework.GDPR)
        assert len(results) == 1
        assert results[0].evidence_name == "data-map"


# ---------------------------------------------------------------------------
# compute_due_dates
# ---------------------------------------------------------------------------


class TestComputeDueDates:
    def test_no_due_date_on_time(self):
        eng = _engine()
        eng.create_schedule(evidence_name="ev1", next_due_at=0.0)
        results = eng.compute_due_dates()
        assert len(results) == 1
        assert results[0]["status"] == ScheduleStatus.ON_TIME.value

    def test_overdue_schedule(self):
        eng = _engine(overdue_grace_days=7)
        past = time.time() - 86400 * 3  # 3 days ago
        eng.create_schedule(evidence_name="ev1", next_due_at=past)
        results = eng.compute_due_dates()
        assert results[0]["status"] == ScheduleStatus.OVERDUE.value

    def test_missed_schedule(self):
        eng = _engine(overdue_grace_days=7)
        far_past = time.time() - 86400 * 15  # 15 days ago
        eng.create_schedule(evidence_name="ev1", next_due_at=far_past)
        results = eng.compute_due_dates()
        assert results[0]["status"] == ScheduleStatus.MISSED.value


# ---------------------------------------------------------------------------
# create_collection_task
# ---------------------------------------------------------------------------


class TestCreateCollectionTask:
    def test_basic_task(self):
        eng = _engine()
        s = eng.create_schedule(evidence_name="access-review")
        task = eng.create_collection_task(schedule_id=s.id)
        assert task is not None
        assert task.schedule_id == s.id
        assert task.evidence_name == "access-review"
        assert task.status == "pending"

    def test_invalid_schedule(self):
        eng = _engine()
        result = eng.create_collection_task(schedule_id="nonexistent")
        assert result is None


# ---------------------------------------------------------------------------
# complete_task
# ---------------------------------------------------------------------------


class TestCompleteTask:
    def test_completes_successfully(self):
        eng = _engine()
        s = eng.create_schedule(evidence_name="access-review")
        task = eng.create_collection_task(schedule_id=s.id)
        result = eng.complete_task(task.id, collected_by="alice")
        assert result is True
        assert task.status == "completed"
        assert task.collected_by == "alice"
        assert task.completed_at > 0

    def test_not_found(self):
        eng = _engine()
        assert eng.complete_task("nonexistent") is False


# ---------------------------------------------------------------------------
# list_tasks
# ---------------------------------------------------------------------------


class TestListTasks:
    def test_list_all(self):
        eng = _engine()
        s = eng.create_schedule(evidence_name="ev1")
        eng.create_collection_task(schedule_id=s.id)
        eng.create_collection_task(schedule_id=s.id)
        assert len(eng.list_tasks()) == 2

    def test_filter_by_status(self):
        eng = _engine()
        s = eng.create_schedule(evidence_name="ev1")
        t1 = eng.create_collection_task(schedule_id=s.id)
        eng.create_collection_task(schedule_id=s.id)
        eng.complete_task(t1.id)
        results = eng.list_tasks(status="completed")
        assert len(results) == 1


# ---------------------------------------------------------------------------
# find_overdue_schedules
# ---------------------------------------------------------------------------


class TestFindOverdueSchedules:
    def test_finds_overdue(self):
        eng = _engine(overdue_grace_days=7)
        past = time.time() - 86400 * 3
        eng.create_schedule(evidence_name="ev1", next_due_at=past)
        eng.create_schedule(evidence_name="ev2", next_due_at=0.0)
        overdue = eng.find_overdue_schedules()
        assert len(overdue) == 1
        assert overdue[0].evidence_name == "ev1"

    def test_none_overdue(self):
        eng = _engine()
        future = time.time() + 86400 * 60
        eng.create_schedule(evidence_name="ev1", next_due_at=future)
        assert len(eng.find_overdue_schedules()) == 0


# ---------------------------------------------------------------------------
# generate_scheduler_report
# ---------------------------------------------------------------------------


class TestGenerateSchedulerReport:
    def test_basic_report(self):
        eng = _engine()
        past = time.time() - 86400 * 3
        eng.create_schedule(
            evidence_name="ev1",
            framework=ComplianceFramework.SOC2,
            next_due_at=past,
        )
        s2 = eng.create_schedule(
            evidence_name="ev2",
            framework=ComplianceFramework.HIPAA,
        )
        t = eng.create_collection_task(schedule_id=s2.id)
        eng.complete_task(t.id)
        report = eng.generate_scheduler_report()
        assert isinstance(report, SchedulerReport)
        assert report.total_schedules == 2
        assert report.total_tasks == 1
        assert report.total_completed == 1
        assert len(report.by_framework) > 0
        assert len(report.recommendations) > 0
        assert report.generated_at > 0

    def test_empty_report(self):
        eng = _engine()
        report = eng.generate_scheduler_report()
        assert report.total_schedules == 0
        assert report.total_tasks == 0
        assert "All evidence collections on schedule" in report.recommendations


# ---------------------------------------------------------------------------
# clear_data
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears_all(self):
        eng = _engine()
        s = eng.create_schedule(evidence_name="ev1")
        eng.create_collection_task(schedule_id=s.id)
        count = eng.clear_data()
        assert count == 1
        assert len(eng._schedules) == 0
        assert len(eng._tasks) == 0


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_schedules"] == 0
        assert stats["total_tasks"] == 0
        assert stats["framework_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.create_schedule(
            evidence_name="ev1",
            framework=ComplianceFramework.SOC2,
        )
        stats = eng.get_stats()
        assert stats["total_schedules"] == 1
        assert stats["overdue_grace_days"] == 7
        assert "soc2" in stats["framework_distribution"]
