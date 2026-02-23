"""Tests for shieldops.observability.status_page -- StatusPageManager."""

from __future__ import annotations

import time

import pytest

from shieldops.observability.status_page import (
    ComponentStatus,
    IncidentUpdate,
    PageVisibility,
    StatusComponent,
    StatusIncident,
    StatusPageManager,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _manager(**kwargs) -> StatusPageManager:
    return StatusPageManager(**kwargs)


# ---------------------------------------------------------------------------
# Enum values
# ---------------------------------------------------------------------------


class TestEnums:
    def test_component_status_operational(self):
        assert ComponentStatus.OPERATIONAL == "operational"

    def test_component_status_degraded(self):
        assert ComponentStatus.DEGRADED == "degraded"

    def test_component_status_partial_outage(self):
        assert ComponentStatus.PARTIAL_OUTAGE == "partial_outage"

    def test_component_status_major_outage(self):
        assert ComponentStatus.MAJOR_OUTAGE == "major_outage"

    def test_component_status_maintenance(self):
        assert ComponentStatus.MAINTENANCE == "maintenance"

    def test_page_visibility_public(self):
        assert PageVisibility.PUBLIC == "public"

    def test_page_visibility_internal(self):
        assert PageVisibility.INTERNAL == "internal"

    def test_page_visibility_private(self):
        assert PageVisibility.PRIVATE == "private"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_status_component_defaults(self):
        c = StatusComponent(name="API")
        assert c.id
        assert c.name == "API"
        assert c.status == ComponentStatus.OPERATIONAL
        assert c.description == ""
        assert c.group == ""
        assert c.display_order == 0
        assert c.visibility == PageVisibility.PUBLIC
        assert c.metadata == {}

    def test_status_incident_defaults(self):
        inc = StatusIncident(title="Outage")
        assert inc.id
        assert inc.title == "Outage"
        assert inc.status == "investigating"
        assert inc.severity == "minor"
        assert inc.affected_components == []
        assert inc.updates == []
        assert inc.resolved_at is None

    def test_incident_update_defaults(self):
        u = IncidentUpdate(incident_id="inc1", message="Looking into it")
        assert u.id
        assert u.incident_id == "inc1"
        assert u.message == "Looking into it"
        assert u.status == "investigating"
        assert u.created_at > 0


# ---------------------------------------------------------------------------
# Create component
# ---------------------------------------------------------------------------


class TestCreateComponent:
    def test_create_basic(self):
        m = _manager()
        c = m.create_component(name="API Gateway")
        assert c.name == "API Gateway"
        assert c.id
        assert c.status == ComponentStatus.OPERATIONAL

    def test_create_with_all_fields(self):
        m = _manager()
        c = m.create_component(
            name="Database",
            description="Primary PostgreSQL cluster",
            group="Backend",
            display_order=5,
            visibility=PageVisibility.INTERNAL,
            metadata={"region": "us-east-1"},
        )
        assert c.description == "Primary PostgreSQL cluster"
        assert c.group == "Backend"
        assert c.display_order == 5
        assert c.visibility == PageVisibility.INTERNAL
        assert c.metadata["region"] == "us-east-1"

    def test_create_max_limit(self):
        m = _manager(max_components=2)
        m.create_component(name="c1")
        m.create_component(name="c2")
        with pytest.raises(ValueError, match="Maximum components"):
            m.create_component(name="c3")

    def test_create_unique_ids(self):
        m = _manager()
        c1 = m.create_component(name="c1")
        c2 = m.create_component(name="c2")
        assert c1.id != c2.id


# ---------------------------------------------------------------------------
# Update component status
# ---------------------------------------------------------------------------


class TestUpdateComponentStatus:
    def test_update_success(self):
        m = _manager()
        c = m.create_component(name="API")
        result = m.update_component_status(c.id, ComponentStatus.DEGRADED)
        assert result is not None
        assert result.status == ComponentStatus.DEGRADED

    def test_update_not_found(self):
        m = _manager()
        result = m.update_component_status("nonexistent", ComponentStatus.DEGRADED)
        assert result is None

    def test_update_changes_updated_at(self):
        m = _manager()
        c = m.create_component(name="API")
        original_updated = c.updated_at
        time.sleep(0.01)
        result = m.update_component_status(c.id, ComponentStatus.MAINTENANCE)
        assert result is not None
        assert result.updated_at >= original_updated


# ---------------------------------------------------------------------------
# Create incident
# ---------------------------------------------------------------------------


class TestCreateIncident:
    def test_create_basic(self):
        m = _manager()
        inc = m.create_incident(title="Database outage")
        assert inc.title == "Database outage"
        assert inc.id
        assert inc.status == "investigating"
        assert inc.severity == "minor"

    def test_create_with_description_and_severity(self):
        m = _manager()
        inc = m.create_incident(
            title="Full outage",
            description="All services affected",
            severity="critical",
        )
        assert inc.description == "All services affected"
        assert inc.severity == "critical"

    def test_create_with_affected_components_updates_status_major(self):
        m = _manager()
        c = m.create_component(name="DB")
        inc = m.create_incident(
            title="DB down",
            severity="major",
            affected_components=[c.id],
        )
        assert c.id in inc.affected_components
        updated = m.list_components()[0]
        assert updated.status == ComponentStatus.MAJOR_OUTAGE

    def test_create_with_affected_components_updates_status_critical(self):
        m = _manager()
        c = m.create_component(name="DB")
        m.create_incident(
            title="DB down",
            severity="critical",
            affected_components=[c.id],
        )
        updated = m.list_components()[0]
        assert updated.status == ComponentStatus.MAJOR_OUTAGE

    def test_create_with_affected_components_minor_severity(self):
        m = _manager()
        c = m.create_component(name="DB")
        m.create_incident(
            title="DB slow",
            severity="minor",
            affected_components=[c.id],
        )
        updated = m.list_components()[0]
        assert updated.status == ComponentStatus.PARTIAL_OUTAGE

    def test_create_max_incidents_limit(self):
        m = _manager(max_incidents=2)
        m.create_incident(title="i1")
        m.create_incident(title="i2")
        with pytest.raises(ValueError, match="Maximum incidents"):
            m.create_incident(title="i3")

    def test_create_with_nonexistent_component_id(self):
        m = _manager()
        inc = m.create_incident(
            title="Incident",
            affected_components=["nonexistent"],
        )
        assert "nonexistent" in inc.affected_components


# ---------------------------------------------------------------------------
# Add incident update
# ---------------------------------------------------------------------------


class TestAddIncidentUpdate:
    def test_add_update_success(self):
        m = _manager()
        inc = m.create_incident(title="Outage")
        update = m.add_incident_update(inc.id, message="Identified root cause")
        assert update is not None
        assert update.message == "Identified root cause"
        assert update.incident_id == inc.id

    def test_add_update_changes_incident_status(self):
        m = _manager()
        inc = m.create_incident(title="Outage")
        m.add_incident_update(inc.id, message="Fix deployed", status="monitoring")
        assert inc.status == "monitoring"

    def test_add_update_not_found(self):
        m = _manager()
        result = m.add_incident_update("nonexistent", message="test")
        assert result is None

    def test_add_multiple_updates(self):
        m = _manager()
        inc = m.create_incident(title="Outage")
        m.add_incident_update(inc.id, message="Investigating")
        m.add_incident_update(inc.id, message="Fix identified", status="identified")
        m.add_incident_update(inc.id, message="Fix deployed", status="monitoring")
        assert len(inc.updates) == 3
        assert inc.status == "monitoring"


# ---------------------------------------------------------------------------
# Resolve incident
# ---------------------------------------------------------------------------


class TestResolveIncident:
    def test_resolve_sets_resolved(self):
        m = _manager()
        inc = m.create_incident(title="Outage")
        result = m.resolve_incident(inc.id)
        assert result is not None
        assert result.status == "resolved"
        assert result.resolved_at is not None

    def test_resolve_restores_components_to_operational(self):
        m = _manager()
        c = m.create_component(name="API")
        inc = m.create_incident(
            title="API down",
            severity="major",
            affected_components=[c.id],
        )
        assert c.status == ComponentStatus.MAJOR_OUTAGE
        m.resolve_incident(inc.id)
        restored = m.list_components()[0]
        assert restored.status == ComponentStatus.OPERATIONAL

    def test_resolve_not_found(self):
        m = _manager()
        result = m.resolve_incident("nonexistent")
        assert result is None

    def test_resolve_with_nonexistent_component_id(self):
        m = _manager()
        inc = m.create_incident(
            title="test",
            affected_components=["nonexistent"],
        )
        result = m.resolve_incident(inc.id)
        assert result is not None
        assert result.status == "resolved"


# ---------------------------------------------------------------------------
# Get page
# ---------------------------------------------------------------------------


class TestGetPage:
    def test_empty_page(self):
        m = _manager()
        page = m.get_page()
        assert page["overall_status"] == "operational"
        assert page["components"] == []
        assert page["active_incidents"] == []

    def test_page_all_operational(self):
        m = _manager()
        m.create_component(name="API")
        m.create_component(name="DB")
        page = m.get_page()
        assert page["overall_status"] == "operational"
        assert len(page["components"]) == 2

    def test_page_major_outage_overall(self):
        m = _manager()
        c = m.create_component(name="API")
        m.update_component_status(c.id, ComponentStatus.MAJOR_OUTAGE)
        page = m.get_page()
        assert page["overall_status"] == "major_outage"

    def test_page_partial_outage_overall(self):
        m = _manager()
        c = m.create_component(name="API")
        m.update_component_status(c.id, ComponentStatus.PARTIAL_OUTAGE)
        page = m.get_page()
        assert page["overall_status"] == "partial_outage"

    def test_page_degraded_overall(self):
        m = _manager()
        c = m.create_component(name="API")
        m.update_component_status(c.id, ComponentStatus.DEGRADED)
        page = m.get_page()
        assert page["overall_status"] == "degraded"

    def test_page_maintenance_overall(self):
        m = _manager()
        c = m.create_component(name="API")
        m.update_component_status(c.id, ComponentStatus.MAINTENANCE)
        page = m.get_page()
        assert page["overall_status"] == "maintenance"

    def test_page_includes_active_incidents(self):
        m = _manager()
        m.create_incident(title="Active one")
        page = m.get_page()
        assert len(page["active_incidents"]) == 1

    def test_page_excludes_resolved_incidents(self):
        m = _manager()
        inc = m.create_incident(title="Resolved one")
        m.resolve_incident(inc.id)
        page = m.get_page()
        assert len(page["active_incidents"]) == 0

    def test_page_components_sorted_by_display_order(self):
        m = _manager()
        m.create_component(name="Third", display_order=3)
        m.create_component(name="First", display_order=1)
        m.create_component(name="Second", display_order=2)
        page = m.get_page()
        names = [c["name"] for c in page["components"]]
        assert names == ["First", "Second", "Third"]


# ---------------------------------------------------------------------------
# List components
# ---------------------------------------------------------------------------


class TestListComponents:
    def test_list_all(self):
        m = _manager()
        m.create_component(name="c1")
        m.create_component(name="c2")
        assert len(m.list_components()) == 2

    def test_list_filter_by_status(self):
        m = _manager()
        c1 = m.create_component(name="c1")
        m.create_component(name="c2")
        m.update_component_status(c1.id, ComponentStatus.DEGRADED)
        degraded = m.list_components(status=ComponentStatus.DEGRADED)
        assert len(degraded) == 1
        assert degraded[0].name == "c1"

    def test_list_empty(self):
        m = _manager()
        assert m.list_components() == []


# ---------------------------------------------------------------------------
# List incidents
# ---------------------------------------------------------------------------


class TestListIncidents:
    def test_list_all(self):
        m = _manager()
        m.create_incident(title="i1")
        m.create_incident(title="i2")
        assert len(m.list_incidents()) == 2

    def test_list_active_only(self):
        m = _manager()
        m.create_incident(title="active")
        resolved_inc = m.create_incident(title="resolved")
        m.resolve_incident(resolved_inc.id)
        active = m.list_incidents(active_only=True)
        assert len(active) == 1
        assert active[0].title == "active"

    def test_list_empty(self):
        m = _manager()
        assert m.list_incidents() == []


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


class TestStats:
    def test_stats_empty(self):
        m = _manager()
        s = m.get_stats()
        assert s["total_components"] == 0
        assert s["operational_components"] == 0
        assert s["total_incidents"] == 0
        assert s["active_incidents"] == 0

    def test_stats_with_data(self):
        m = _manager()
        c = m.create_component(name="API")
        m.create_component(name="DB")
        m.create_incident(
            title="API down",
            severity="major",
            affected_components=[c.id],
        )
        s = m.get_stats()
        assert s["total_components"] == 2
        assert s["operational_components"] == 1
        assert s["total_incidents"] == 1
        assert s["active_incidents"] == 1

    def test_stats_resolved_incident_not_active(self):
        m = _manager()
        inc = m.create_incident(title="Resolved")
        m.resolve_incident(inc.id)
        s = m.get_stats()
        assert s["active_incidents"] == 0
        assert s["total_incidents"] == 1
