"""Status page management for service health communication.

Manages service component statuses, incidents, and incident updates to power
internal and public-facing status pages with real-time health information.
"""

from __future__ import annotations

import enum
import time
import uuid
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# -- Enums --------------------------------------------------------------------


class ComponentStatus(enum.StrEnum):
    OPERATIONAL = "operational"
    DEGRADED = "degraded"
    PARTIAL_OUTAGE = "partial_outage"
    MAJOR_OUTAGE = "major_outage"
    MAINTENANCE = "maintenance"


class PageVisibility(enum.StrEnum):
    PUBLIC = "public"
    INTERNAL = "internal"
    PRIVATE = "private"


# -- Models --------------------------------------------------------------------


class StatusComponent(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str
    description: str = ""
    status: ComponentStatus = ComponentStatus.OPERATIONAL
    group: str = ""
    display_order: int = 0
    visibility: PageVisibility = PageVisibility.PUBLIC
    metadata: dict[str, Any] = Field(default_factory=dict)
    updated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


class IncidentUpdate(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    incident_id: str
    message: str
    status: str = "investigating"
    created_at: float = Field(default_factory=time.time)


class StatusIncident(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    title: str
    description: str = ""
    status: str = "investigating"
    severity: str = "minor"
    affected_components: list[str] = Field(default_factory=list)
    updates: list[IncidentUpdate] = Field(default_factory=list)
    resolved_at: float | None = None
    created_at: float = Field(default_factory=time.time)


# -- Manager -------------------------------------------------------------------


class StatusPageManager:
    """Manage service status components, incidents, and status page rendering.

    Parameters
    ----------
    max_components:
        Maximum number of status components to track.
    max_incidents:
        Maximum number of incidents to store.
    """

    def __init__(
        self,
        max_components: int = 200,
        max_incidents: int = 1000,
    ) -> None:
        self._components: dict[str, StatusComponent] = {}
        self._incidents: dict[str, StatusIncident] = {}
        self._max_components = max_components
        self._max_incidents = max_incidents

    def create_component(
        self,
        name: str,
        description: str = "",
        group: str = "",
        display_order: int = 0,
        visibility: PageVisibility = PageVisibility.PUBLIC,
        metadata: dict[str, Any] | None = None,
    ) -> StatusComponent:
        if len(self._components) >= self._max_components:
            raise ValueError(f"Maximum components limit reached: {self._max_components}")
        component = StatusComponent(
            name=name,
            description=description,
            group=group,
            display_order=display_order,
            visibility=visibility,
            metadata=metadata or {},
        )
        self._components[component.id] = component
        logger.info("status_component_created", component_id=component.id, name=name)
        return component

    def update_component_status(
        self,
        component_id: str,
        status: ComponentStatus,
    ) -> StatusComponent | None:
        component = self._components.get(component_id)
        if component is None:
            return None
        component.status = status
        component.updated_at = time.time()
        logger.info(
            "component_status_updated",
            component_id=component_id,
            status=status,
        )
        return component

    def create_incident(
        self,
        title: str,
        description: str = "",
        severity: str = "minor",
        affected_components: list[str] | None = None,
    ) -> StatusIncident:
        if len(self._incidents) >= self._max_incidents:
            raise ValueError(f"Maximum incidents limit reached: {self._max_incidents}")
        incident = StatusIncident(
            title=title,
            description=description,
            severity=severity,
            affected_components=affected_components or [],
        )
        self._incidents[incident.id] = incident

        # Update affected component statuses based on severity
        target_status = (
            ComponentStatus.MAJOR_OUTAGE
            if severity in ("major", "critical")
            else ComponentStatus.PARTIAL_OUTAGE
        )
        for comp_id in incident.affected_components:
            comp = self._components.get(comp_id)
            if comp is not None:
                comp.status = target_status
                comp.updated_at = time.time()

        logger.info(
            "status_incident_created",
            incident_id=incident.id,
            title=title,
            severity=severity,
        )
        return incident

    def add_incident_update(
        self,
        incident_id: str,
        message: str,
        status: str = "investigating",
    ) -> IncidentUpdate | None:
        incident = self._incidents.get(incident_id)
        if incident is None:
            return None
        update = IncidentUpdate(
            incident_id=incident_id,
            message=message,
            status=status,
        )
        incident.updates.append(update)
        incident.status = status
        logger.info(
            "incident_update_added",
            incident_id=incident_id,
            update_id=update.id,
            status=status,
        )
        return update

    def resolve_incident(self, incident_id: str) -> StatusIncident | None:
        incident = self._incidents.get(incident_id)
        if incident is None:
            return None
        incident.status = "resolved"
        incident.resolved_at = time.time()

        # Restore affected components to OPERATIONAL
        for comp_id in incident.affected_components:
            comp = self._components.get(comp_id)
            if comp is not None:
                comp.status = ComponentStatus.OPERATIONAL
                comp.updated_at = time.time()

        logger.info("incident_resolved", incident_id=incident_id)
        return incident

    def get_page(self) -> dict[str, Any]:
        components = sorted(self._components.values(), key=lambda c: c.display_order)
        active_incidents = [inc for inc in self._incidents.values() if inc.resolved_at is None]

        # Determine overall status
        if any(c.status == ComponentStatus.MAJOR_OUTAGE for c in components):
            overall = "major_outage"
        elif any(c.status == ComponentStatus.PARTIAL_OUTAGE for c in components):
            overall = "partial_outage"
        elif any(c.status == ComponentStatus.DEGRADED for c in components):
            overall = "degraded"
        elif any(c.status == ComponentStatus.MAINTENANCE for c in components):
            overall = "maintenance"
        else:
            overall = "operational"

        return {
            "overall_status": overall,
            "components": [c.model_dump() for c in components],
            "active_incidents": [inc.model_dump() for inc in active_incidents],
        }

    def list_components(
        self,
        status: ComponentStatus | None = None,
    ) -> list[StatusComponent]:
        components = list(self._components.values())
        if status:
            components = [c for c in components if c.status == status]
        return components

    def list_incidents(self, active_only: bool = False) -> list[StatusIncident]:
        incidents = list(self._incidents.values())
        if active_only:
            incidents = [inc for inc in incidents if inc.resolved_at is None]
        return incidents

    def get_stats(self) -> dict[str, Any]:
        active_incidents = sum(1 for inc in self._incidents.values() if inc.resolved_at is None)
        operational = sum(
            1 for c in self._components.values() if c.status == ComponentStatus.OPERATIONAL
        )
        return {
            "total_components": len(self._components),
            "operational_components": operational,
            "total_incidents": len(self._incidents),
            "active_incidents": active_incidents,
        }
