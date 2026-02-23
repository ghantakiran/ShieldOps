"""Tests for the PostMortemGenerator.

Covers:
- PostMortemGenerator creation and defaults
- generate() with full params, minimal params, max limit reached
- get_report() found and not found
- list_reports() with/without status filter, limit
- update_status() to each status, not found, PUBLISHED sets published_at
- add_action_item() with all params, not found
- update_action_item() status change, assignee change, not found
- get_open_action_items() with mixed statuses
- get_stats() counts
- Severity enum values
- PostMortemStatus enum values
- ActionItemStatus enum values
- ContributingFactor model
- Edge cases: empty contributing factors, empty lessons_learned
"""

from __future__ import annotations

import time

import pytest

from shieldops.agents.investigation.postmortem import (
    ActionItem,
    ActionItemStatus,
    ContributingFactor,
    PostMortemGenerator,
    PostMortemReport,
    PostMortemStatus,
    Severity,
)

# ── Helpers ───────────────────────────────────────────────────────


def _generate_report(
    gen: PostMortemGenerator,
    incident_id: str = "INC-001",
    title: str = "Service Outage",
    **kwargs,
) -> PostMortemReport:
    return gen.generate(incident_id=incident_id, title=title, **kwargs)


# ── Enum Tests ────────────────────────────────────────────────────


class TestSeverityEnum:
    def test_low_value(self) -> None:
        assert Severity.LOW == "low"

    def test_medium_value(self) -> None:
        assert Severity.MEDIUM == "medium"

    def test_high_value(self) -> None:
        assert Severity.HIGH == "high"

    def test_critical_value(self) -> None:
        assert Severity.CRITICAL == "critical"

    def test_enum_member_count(self) -> None:
        assert len(Severity) == 4


class TestPostMortemStatusEnum:
    def test_draft_value(self) -> None:
        assert PostMortemStatus.DRAFT == "draft"

    def test_in_review_value(self) -> None:
        assert PostMortemStatus.IN_REVIEW == "in_review"

    def test_published_value(self) -> None:
        assert PostMortemStatus.PUBLISHED == "published"

    def test_archived_value(self) -> None:
        assert PostMortemStatus.ARCHIVED == "archived"

    def test_enum_member_count(self) -> None:
        assert len(PostMortemStatus) == 4


class TestActionItemStatusEnum:
    def test_open_value(self) -> None:
        assert ActionItemStatus.OPEN == "open"

    def test_in_progress_value(self) -> None:
        assert ActionItemStatus.IN_PROGRESS == "in_progress"

    def test_completed_value(self) -> None:
        assert ActionItemStatus.COMPLETED == "completed"

    def test_wont_fix_value(self) -> None:
        assert ActionItemStatus.WONT_FIX == "wont_fix"


# ── Model Tests ───────────────────────────────────────────────────


class TestContributingFactorModel:
    def test_defaults(self) -> None:
        cf = ContributingFactor(description="Disk full")
        assert cf.description == "Disk full"
        assert cf.category == ""
        assert cf.is_root_cause is False
        assert len(cf.id) == 12

    def test_with_all_fields(self) -> None:
        cf = ContributingFactor(
            description="Misconfigured autoscaler",
            category="configuration",
            is_root_cause=True,
        )
        assert cf.is_root_cause is True
        assert cf.category == "configuration"


class TestActionItemModel:
    def test_defaults(self) -> None:
        item = ActionItem(title="Fix autoscaler")
        assert item.title == "Fix autoscaler"
        assert item.description == ""
        assert item.assignee == ""
        assert item.status == ActionItemStatus.OPEN
        assert item.priority == "medium"
        assert item.due_date == ""
        assert item.created_at > 0
        assert item.updated_at > 0


# ── Generator Creation ────────────────────────────────────────────


class TestPostMortemGeneratorCreation:
    def test_default_max_reports(self) -> None:
        gen = PostMortemGenerator()
        assert gen._max_reports == 1000

    def test_custom_max_reports(self) -> None:
        gen = PostMortemGenerator(max_reports=5)
        assert gen._max_reports == 5

    def test_empty_reports_on_init(self) -> None:
        gen = PostMortemGenerator()
        assert len(gen._reports) == 0


# ── generate() ────────────────────────────────────────────────────


class TestGenerate:
    def test_minimal_params(self) -> None:
        gen = PostMortemGenerator()
        report = gen.generate(incident_id="INC-001", title="Outage")
        assert report.incident_id == "INC-001"
        assert report.title == "Outage"
        assert report.summary == ""
        assert report.severity == Severity.MEDIUM
        assert report.status == PostMortemStatus.DRAFT
        assert report.contributing_factors == []
        assert report.lessons_learned == []
        assert report.services_affected == []
        assert report.duration_minutes == 0.0
        assert report.published_at is None

    def test_full_params(self) -> None:
        gen = PostMortemGenerator()
        factors = [{"description": "Disk full", "category": "infra", "is_root_cause": True}]
        report = gen.generate(
            incident_id="INC-002",
            title="DB Crash",
            summary="Database crashed due to full disk",
            severity=Severity.CRITICAL,
            contributing_factors=factors,
            timeline_summary="0900: Alert triggered",
            impact_description="100% of users affected",
            detection_method="Prometheus alert",
            resolution_summary="Disk expanded and service restarted",
            lessons_learned=["Add disk monitoring", "Set up auto-expand"],
            services_affected=["db-primary", "api-gateway"],
            duration_minutes=45.5,
            metadata={"team": "platform"},
        )
        assert report.severity == Severity.CRITICAL
        assert report.summary == "Database crashed due to full disk"
        assert len(report.contributing_factors) == 1
        assert report.contributing_factors[0].is_root_cause is True
        assert report.timeline_summary == "0900: Alert triggered"
        assert report.impact_description == "100% of users affected"
        assert report.detection_method == "Prometheus alert"
        assert report.resolution_summary == "Disk expanded and service restarted"
        assert report.lessons_learned == ["Add disk monitoring", "Set up auto-expand"]
        assert report.services_affected == ["db-primary", "api-gateway"]
        assert report.duration_minutes == pytest.approx(45.5)
        assert report.metadata == {"team": "platform"}

    def test_report_stored_in_dict(self) -> None:
        gen = PostMortemGenerator()
        report = _generate_report(gen)
        assert gen.get_report(report.id) is report

    def test_report_has_unique_id(self) -> None:
        gen = PostMortemGenerator()
        r1 = _generate_report(gen, incident_id="INC-1")
        r2 = _generate_report(gen, incident_id="INC-2")
        assert r1.id != r2.id

    def test_max_limit_raises_value_error(self) -> None:
        gen = PostMortemGenerator(max_reports=2)
        _generate_report(gen, incident_id="INC-1")
        _generate_report(gen, incident_id="INC-2")
        with pytest.raises(ValueError, match="Maximum reports limit reached"):
            _generate_report(gen, incident_id="INC-3")

    def test_empty_contributing_factors_list(self) -> None:
        gen = PostMortemGenerator()
        report = gen.generate(incident_id="INC-1", title="Test", contributing_factors=[])
        assert report.contributing_factors == []

    def test_empty_lessons_learned(self) -> None:
        gen = PostMortemGenerator()
        report = gen.generate(incident_id="INC-1", title="Test", lessons_learned=[])
        assert report.lessons_learned == []

    def test_created_at_set(self) -> None:
        gen = PostMortemGenerator()
        before = time.time()
        report = _generate_report(gen)
        after = time.time()
        assert before <= report.created_at <= after


# ── get_report() ──────────────────────────────────────────────────


class TestGetReport:
    def test_found(self) -> None:
        gen = PostMortemGenerator()
        report = _generate_report(gen)
        assert gen.get_report(report.id) is report

    def test_not_found(self) -> None:
        gen = PostMortemGenerator()
        assert gen.get_report("nonexistent") is None


# ── list_reports() ────────────────────────────────────────────────


class TestListReports:
    def test_returns_all_reports(self) -> None:
        gen = PostMortemGenerator()
        _generate_report(gen, incident_id="INC-1")
        _generate_report(gen, incident_id="INC-2")
        _generate_report(gen, incident_id="INC-3")
        reports = gen.list_reports()
        assert len(reports) == 3

    def test_filter_by_status(self) -> None:
        gen = PostMortemGenerator()
        r1 = _generate_report(gen, incident_id="INC-1")
        _generate_report(gen, incident_id="INC-2")
        gen.update_status(r1.id, PostMortemStatus.PUBLISHED)
        published = gen.list_reports(status=PostMortemStatus.PUBLISHED)
        assert len(published) == 1
        assert published[0].id == r1.id

    def test_limit(self) -> None:
        gen = PostMortemGenerator()
        for i in range(5):
            _generate_report(gen, incident_id=f"INC-{i}")
        reports = gen.list_reports(limit=3)
        assert len(reports) == 3

    def test_sorted_by_created_at_descending(self) -> None:
        gen = PostMortemGenerator()
        _generate_report(gen, incident_id="INC-1")
        _generate_report(gen, incident_id="INC-2")
        reports = gen.list_reports()
        assert reports[0].created_at >= reports[1].created_at

    def test_empty_when_no_reports(self) -> None:
        gen = PostMortemGenerator()
        assert gen.list_reports() == []


# ── update_status() ──────────────────────────────────────────────


class TestUpdateStatus:
    def test_to_in_review(self) -> None:
        gen = PostMortemGenerator()
        report = _generate_report(gen)
        result = gen.update_status(report.id, PostMortemStatus.IN_REVIEW)
        assert result is not None
        assert result.status == PostMortemStatus.IN_REVIEW

    def test_to_published_sets_published_at(self) -> None:
        gen = PostMortemGenerator()
        report = _generate_report(gen)
        assert report.published_at is None
        before = time.time()
        result = gen.update_status(report.id, PostMortemStatus.PUBLISHED)
        after = time.time()
        assert result is not None
        assert result.published_at is not None
        assert before <= result.published_at <= after

    def test_to_archived(self) -> None:
        gen = PostMortemGenerator()
        report = _generate_report(gen)
        result = gen.update_status(report.id, PostMortemStatus.ARCHIVED)
        assert result is not None
        assert result.status == PostMortemStatus.ARCHIVED

    def test_to_draft(self) -> None:
        gen = PostMortemGenerator()
        report = _generate_report(gen)
        gen.update_status(report.id, PostMortemStatus.PUBLISHED)
        result = gen.update_status(report.id, PostMortemStatus.DRAFT)
        assert result is not None
        assert result.status == PostMortemStatus.DRAFT

    def test_not_found_returns_none(self) -> None:
        gen = PostMortemGenerator()
        assert gen.update_status("missing", PostMortemStatus.PUBLISHED) is None

    def test_updates_updated_at(self) -> None:
        gen = PostMortemGenerator()
        report = _generate_report(gen)
        old_updated = report.updated_at
        time.sleep(0.01)
        gen.update_status(report.id, PostMortemStatus.IN_REVIEW)
        assert report.updated_at >= old_updated


# ── add_action_item() ────────────────────────────────────────────


class TestAddActionItem:
    def test_with_all_params(self) -> None:
        gen = PostMortemGenerator()
        report = _generate_report(gen)
        item = gen.add_action_item(
            report_id=report.id,
            title="Add disk monitoring",
            description="Set up Prometheus disk alerts",
            assignee="alice@example.com",
            priority="high",
            due_date="2026-03-01",
        )
        assert item is not None
        assert item.title == "Add disk monitoring"
        assert item.description == "Set up Prometheus disk alerts"
        assert item.assignee == "alice@example.com"
        assert item.priority == "high"
        assert item.due_date == "2026-03-01"
        assert item.status == ActionItemStatus.OPEN

    def test_appended_to_report(self) -> None:
        gen = PostMortemGenerator()
        report = _generate_report(gen)
        gen.add_action_item(report.id, title="Task 1")
        gen.add_action_item(report.id, title="Task 2")
        assert len(report.action_items) == 2

    def test_not_found_returns_none(self) -> None:
        gen = PostMortemGenerator()
        assert gen.add_action_item("missing", title="Task") is None

    def test_updates_report_updated_at(self) -> None:
        gen = PostMortemGenerator()
        report = _generate_report(gen)
        old_updated = report.updated_at
        time.sleep(0.01)
        gen.add_action_item(report.id, title="Task")
        assert report.updated_at >= old_updated


# ── update_action_item() ─────────────────────────────────────────


class TestUpdateActionItem:
    def test_status_change(self) -> None:
        gen = PostMortemGenerator()
        report = _generate_report(gen)
        item = gen.add_action_item(report.id, title="Fix bug")
        assert item is not None
        result = gen.update_action_item(report.id, item.id, status=ActionItemStatus.COMPLETED)
        assert result is not None
        assert result.status == ActionItemStatus.COMPLETED

    def test_assignee_change(self) -> None:
        gen = PostMortemGenerator()
        report = _generate_report(gen)
        item = gen.add_action_item(report.id, title="Fix bug", assignee="alice")
        assert item is not None
        result = gen.update_action_item(report.id, item.id, assignee="bob")
        assert result is not None
        assert result.assignee == "bob"

    def test_report_not_found_returns_none(self) -> None:
        gen = PostMortemGenerator()
        result = gen.update_action_item(
            "missing",
            "item-1",
            status=ActionItemStatus.COMPLETED,
        )
        assert result is None

    def test_item_not_found_returns_none(self) -> None:
        gen = PostMortemGenerator()
        report = _generate_report(gen)
        assert gen.update_action_item(report.id, "missing-item") is None

    def test_updates_item_updated_at(self) -> None:
        gen = PostMortemGenerator()
        report = _generate_report(gen)
        item = gen.add_action_item(report.id, title="Fix bug")
        assert item is not None
        old_updated = item.updated_at
        time.sleep(0.01)
        gen.update_action_item(report.id, item.id, status=ActionItemStatus.IN_PROGRESS)
        assert item.updated_at >= old_updated


# ── get_open_action_items() ──────────────────────────────────────


class TestGetOpenActionItems:
    def test_returns_open_and_in_progress(self) -> None:
        gen = PostMortemGenerator()
        report = _generate_report(gen)
        gen.add_action_item(report.id, title="Open task")
        item_ip = gen.add_action_item(report.id, title="In progress task")
        assert item_ip is not None
        gen.update_action_item(report.id, item_ip.id, status=ActionItemStatus.IN_PROGRESS)
        item_done = gen.add_action_item(report.id, title="Done task")
        assert item_done is not None
        gen.update_action_item(report.id, item_done.id, status=ActionItemStatus.COMPLETED)
        item_wf = gen.add_action_item(report.id, title="Wont fix task")
        assert item_wf is not None
        gen.update_action_item(report.id, item_wf.id, status=ActionItemStatus.WONT_FIX)

        open_items = gen.get_open_action_items()
        assert len(open_items) == 2
        titles = {i["title"] for i in open_items}
        assert titles == {"Open task", "In progress task"}

    def test_includes_report_id_and_incident_id(self) -> None:
        gen = PostMortemGenerator()
        report = gen.generate(incident_id="INC-099", title="Test")
        gen.add_action_item(report.id, title="Task A")
        items = gen.get_open_action_items()
        assert len(items) == 1
        assert items[0]["report_id"] == report.id
        assert items[0]["incident_id"] == "INC-099"

    def test_empty_when_all_closed(self) -> None:
        gen = PostMortemGenerator()
        report = _generate_report(gen)
        item = gen.add_action_item(report.id, title="Task")
        assert item is not None
        gen.update_action_item(report.id, item.id, status=ActionItemStatus.COMPLETED)
        assert gen.get_open_action_items() == []

    def test_empty_when_no_items(self) -> None:
        gen = PostMortemGenerator()
        _generate_report(gen)
        assert gen.get_open_action_items() == []


# ── get_stats() ──────────────────────────────────────────────────


class TestGetStats:
    def test_empty_stats(self) -> None:
        gen = PostMortemGenerator()
        stats = gen.get_stats()
        assert stats["total_reports"] == 0
        assert stats["by_status"] == {}
        assert stats["total_action_items"] == 0
        assert stats["open_action_items"] == 0

    def test_counts_reports_and_action_items(self) -> None:
        gen = PostMortemGenerator()
        r1 = _generate_report(gen, incident_id="INC-1")
        r2 = _generate_report(gen, incident_id="INC-2")
        gen.add_action_item(r1.id, title="T1")
        gen.add_action_item(r1.id, title="T2")
        gen.add_action_item(r2.id, title="T3")
        stats = gen.get_stats()
        assert stats["total_reports"] == 2
        assert stats["total_action_items"] == 3
        assert stats["open_action_items"] == 3

    def test_by_status_breakdown(self) -> None:
        gen = PostMortemGenerator()
        r1 = _generate_report(gen, incident_id="INC-1")
        _generate_report(gen, incident_id="INC-2")
        gen.update_status(r1.id, PostMortemStatus.PUBLISHED)
        stats = gen.get_stats()
        assert stats["by_status"]["published"] == 1
        assert stats["by_status"]["draft"] == 1

    def test_open_action_items_excludes_completed(self) -> None:
        gen = PostMortemGenerator()
        report = _generate_report(gen)
        item = gen.add_action_item(report.id, title="T1")
        assert item is not None
        gen.update_action_item(report.id, item.id, status=ActionItemStatus.COMPLETED)
        gen.add_action_item(report.id, title="T2")
        stats = gen.get_stats()
        assert stats["total_action_items"] == 2
        assert stats["open_action_items"] == 1
