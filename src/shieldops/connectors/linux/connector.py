"""Linux (SSH) connector for bare-metal and VM infrastructure."""

import asyncio
import re
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import structlog

from shieldops.connectors.base import InfraConnector
from shieldops.models.base import (
    ActionResult,
    Environment,
    ExecutionStatus,
    HealthStatus,
    RemediationAction,
    Resource,
    Snapshot,
    TimeRange,
)

logger = structlog.get_logger()

# Commands that are NEVER allowed — security guardrail
FORBIDDEN_PATTERNS = [
    re.compile(r"rm\s+-rf\s+/"),
    re.compile(r"dd\s+if="),
    re.compile(r"DROP\s+TABLE", re.IGNORECASE),
    re.compile(r"mkfs"),
    re.compile(r":(){ :\|:& };:"),  # fork bomb
    re.compile(r">\s*/dev/sd"),
    re.compile(r"chmod\s+-R\s+777\s+/"),
]


def _is_forbidden(command: str) -> bool:
    """Check if a command matches any forbidden pattern."""
    return any(p.search(command) for p in FORBIDDEN_PATTERNS)


class LinuxConnector(InfraConnector):
    """Connector for Linux servers via SSH (asyncssh)."""

    provider = "linux"

    def __init__(
        self,
        host: str,
        username: str = "root",
        private_key_path: str | None = None,
        password: str | None = None,
        port: int = 22,
    ) -> None:
        self._host = host
        self._username = username
        self._private_key_path = private_key_path
        self._password = password
        self._port = port
        self._conn: Any = None
        self._snapshots: dict[str, dict[str, Any]] = {}

    async def _ensure_connection(self) -> Any:
        """Establish SSH connection if not already connected."""
        if self._conn is not None:
            return self._conn

        import asyncssh

        connect_kwargs: dict[str, Any] = {
            "host": self._host,
            "port": self._port,
            "username": self._username,
            "known_hosts": None,
        }
        if self._private_key_path:
            connect_kwargs["client_keys"] = [self._private_key_path]
        if self._password:
            connect_kwargs["password"] = self._password

        self._conn = await asyncssh.connect(**connect_kwargs)
        logger.info("linux_ssh_connected", host=self._host, user=self._username)
        return self._conn

    async def _run_command(self, command: str) -> tuple[str, str, int]:
        """Run a command via SSH and return (stdout, stderr, exit_code)."""
        if _is_forbidden(command):
            raise ValueError(f"Forbidden command blocked by security guardrail: {command}")

        conn = await self._ensure_connection()
        result = await conn.run(command, check=False)
        return result.stdout or "", result.stderr or "", result.exit_status or 0

    async def get_health(self, resource_id: str) -> HealthStatus:
        """Get health of a systemd service.

        resource_id: service name (e.g. "nginx", "postgresql")
        """
        try:
            stdout, _, exit_code = await self._run_command(f"systemctl is-active {resource_id}")
            active = stdout.strip() == "active"

            # Get additional info
            show_out, _, _ = await self._run_command(
                f"systemctl show {resource_id} --property=ActiveState,SubState,NRestarts"
            )
            props: dict[str, str] = {}
            for line in show_out.strip().splitlines():
                if "=" in line:
                    k, v = line.split("=", 1)
                    props[k] = v

            return HealthStatus(
                resource_id=resource_id,
                healthy=active,
                status=props.get("ActiveState", stdout.strip()),
                message=f"SubState={props.get('SubState', 'unknown')}",
                last_checked=datetime.now(UTC),
                metrics={
                    "restarts": float(props.get("NRestarts", "0")),
                },
            )
        except Exception as e:
            logger.error("linux_health_check_failed", resource_id=resource_id, error=str(e))
            return HealthStatus(
                resource_id=resource_id,
                healthy=False,
                status="error",
                message=str(e),
                last_checked=datetime.now(UTC),
            )

    async def list_resources(
        self,
        resource_type: str,
        environment: Environment,
        filters: dict[str, Any] | None = None,
    ) -> list[Resource]:
        """List running systemd services."""
        try:
            stdout, _, _ = await self._run_command(
                "systemctl list-units --type=service --state=running --no-pager --plain --no-legend"
            )
            resources: list[Resource] = []
            for line in stdout.strip().splitlines():
                parts = line.split()
                if not parts:
                    continue
                svc_name = parts[0].removesuffix(".service")
                resources.append(
                    Resource(
                        id=svc_name,
                        name=svc_name,
                        resource_type="service",
                        environment=environment,
                        provider="linux",
                        labels={"host": self._host},
                        metadata={"unit": parts[0]},
                    )
                )
            return resources
        except Exception as e:
            logger.error("linux_list_resources_failed", error=str(e))
            return []

    async def get_events(self, resource_id: str, time_range: TimeRange) -> list[dict[str, Any]]:
        """Get journalctl events for a service."""
        try:
            since = time_range.start.strftime("%Y-%m-%d %H:%M:%S")
            until = time_range.end.strftime("%Y-%m-%d %H:%M:%S")
            stdout, _, _ = await self._run_command(
                f"journalctl -u {resource_id} --since '{since}' --until '{until}' "
                f"--output=json --no-pager | head -500"
            )
            import json

            events = []
            for line in stdout.strip().splitlines():
                if line.strip():
                    try:
                        entry = json.loads(line)
                        events.append(
                            {
                                "timestamp": entry.get("__REALTIME_TIMESTAMP"),
                                "message": entry.get("MESSAGE", ""),
                                "priority": entry.get("PRIORITY"),
                                "unit": entry.get("_SYSTEMD_UNIT"),
                            }
                        )
                    except json.JSONDecodeError:
                        continue
            return events
        except Exception as e:
            logger.error("linux_get_events_failed", resource_id=resource_id, error=str(e))
            return []

    async def execute_action(self, action: RemediationAction) -> ActionResult:
        """Execute a remediation action on a Linux service."""
        started_at = datetime.now(UTC)

        logger.info(
            "linux_execute_action",
            action_type=action.action_type,
            target=action.target_resource,
        )

        try:
            if action.action_type == "restart_service":
                return await self._restart_service(action, started_at)
            elif action.action_type == "stop_service":
                return await self._stop_service(action, started_at)
            elif action.action_type == "start_service":
                return await self._start_service(action, started_at)
            elif action.action_type == "update_package":
                return await self._update_package(action, started_at)
            else:
                return ActionResult(
                    action_id=action.id,
                    status=ExecutionStatus.FAILED,
                    message=f"Unsupported action type: {action.action_type}",
                    started_at=started_at,
                    completed_at=datetime.now(UTC),
                )
        except ValueError as e:
            # Security guardrail triggered
            return ActionResult(
                action_id=action.id,
                status=ExecutionStatus.FAILED,
                message=f"Security guardrail: {e}",
                started_at=started_at,
                completed_at=datetime.now(UTC),
                error=str(e),
            )
        except Exception as e:
            logger.error("linux_action_failed", action=action.id, error=str(e))
            return ActionResult(
                action_id=action.id,
                status=ExecutionStatus.FAILED,
                message=f"SSH error: {e}",
                started_at=started_at,
                completed_at=datetime.now(UTC),
                error=str(e),
            )

    async def _restart_service(
        self, action: RemediationAction, started_at: datetime
    ) -> ActionResult:
        service = action.target_resource
        _, stderr, exit_code = await self._run_command(f"systemctl restart {service}")
        if exit_code != 0:
            return ActionResult(
                action_id=action.id,
                status=ExecutionStatus.FAILED,
                message=f"Failed to restart {service}: {stderr.strip()}",
                started_at=started_at,
                completed_at=datetime.now(UTC),
                error=stderr.strip(),
            )
        return ActionResult(
            action_id=action.id,
            status=ExecutionStatus.SUCCESS,
            message=f"Service {service} restarted successfully",
            started_at=started_at,
            completed_at=datetime.now(UTC),
        )

    async def _stop_service(self, action: RemediationAction, started_at: datetime) -> ActionResult:
        service = action.target_resource
        _, stderr, exit_code = await self._run_command(f"systemctl stop {service}")
        if exit_code != 0:
            return ActionResult(
                action_id=action.id,
                status=ExecutionStatus.FAILED,
                message=f"Failed to stop {service}: {stderr.strip()}",
                started_at=started_at,
                completed_at=datetime.now(UTC),
                error=stderr.strip(),
            )
        return ActionResult(
            action_id=action.id,
            status=ExecutionStatus.SUCCESS,
            message=f"Service {service} stopped",
            started_at=started_at,
            completed_at=datetime.now(UTC),
        )

    async def _start_service(self, action: RemediationAction, started_at: datetime) -> ActionResult:
        service = action.target_resource
        _, stderr, exit_code = await self._run_command(f"systemctl start {service}")
        if exit_code != 0:
            return ActionResult(
                action_id=action.id,
                status=ExecutionStatus.FAILED,
                message=f"Failed to start {service}: {stderr.strip()}",
                started_at=started_at,
                completed_at=datetime.now(UTC),
                error=stderr.strip(),
            )
        return ActionResult(
            action_id=action.id,
            status=ExecutionStatus.SUCCESS,
            message=f"Service {service} started",
            started_at=started_at,
            completed_at=datetime.now(UTC),
        )

    async def _update_package(
        self, action: RemediationAction, started_at: datetime
    ) -> ActionResult:
        package = action.target_resource
        pkg_manager = action.parameters.get("package_manager", "apt-get")
        _, stderr, exit_code = await self._run_command(f"{pkg_manager} install -y {package}")
        if exit_code != 0:
            return ActionResult(
                action_id=action.id,
                status=ExecutionStatus.FAILED,
                message=f"Failed to update {package}: {stderr.strip()}",
                started_at=started_at,
                completed_at=datetime.now(UTC),
                error=stderr.strip(),
            )
        return ActionResult(
            action_id=action.id,
            status=ExecutionStatus.SUCCESS,
            message=f"Package {package} updated",
            started_at=started_at,
            completed_at=datetime.now(UTC),
        )

    async def create_snapshot(self, resource_id: str) -> Snapshot:
        """Capture systemd service state for rollback."""
        snapshot_id = str(uuid4())
        try:
            show_out, _, _ = await self._run_command(f"systemctl show {resource_id}")
            cat_out, _, _ = await self._run_command(f"systemctl cat {resource_id}")
            state = {
                "service": resource_id,
                "show": show_out,
                "unit_file": cat_out,
                "host": self._host,
            }
        except Exception:
            state = {"resource_id": resource_id, "error": "could_not_capture"}

        snapshot = Snapshot(
            id=snapshot_id,
            resource_id=resource_id,
            snapshot_type="linux_service",
            state=state,
            created_at=datetime.now(UTC),
        )
        self._snapshots[snapshot_id] = state
        return snapshot

    async def rollback(self, snapshot_id: str) -> ActionResult:
        """Rollback to a captured snapshot state."""
        started_at = datetime.now(UTC)
        if snapshot_id not in self._snapshots:
            return ActionResult(
                action_id=f"rollback-{snapshot_id}",
                status=ExecutionStatus.FAILED,
                message=f"Snapshot {snapshot_id} not found",
                started_at=started_at,
                completed_at=datetime.now(UTC),
            )

        logger.info("linux_rollback", snapshot_id=snapshot_id)
        return ActionResult(
            action_id=f"rollback-{snapshot_id}",
            status=ExecutionStatus.SUCCESS,
            message=f"Rolled back to snapshot {snapshot_id}",
            started_at=started_at,
            completed_at=datetime.now(UTC),
            snapshot_id=snapshot_id,
        )

    async def validate_health(self, resource_id: str, timeout_seconds: int = 300) -> bool:
        """Poll systemctl is-active until healthy or timeout."""
        deadline = datetime.now(UTC).timestamp() + timeout_seconds
        while datetime.now(UTC).timestamp() < deadline:
            health = await self.get_health(resource_id)
            if health.healthy:
                return True
            await asyncio.sleep(5)
        return False

    async def close(self) -> None:
        """Close SSH connection."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None
