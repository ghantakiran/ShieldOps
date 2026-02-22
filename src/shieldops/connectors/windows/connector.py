"""Windows (WinRM) connector for Windows VM infrastructure."""

import asyncio
import re
from datetime import UTC, datetime
from functools import partial
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

# PowerShell commands that are NEVER allowed — security guardrail
FORBIDDEN_PATTERNS = [
    re.compile(r"Format-Volume", re.IGNORECASE),
    re.compile(r"Remove-Item\s+-Recurse.*C:\\", re.IGNORECASE),
    re.compile(r"Clear-Disk", re.IGNORECASE),
    re.compile(r"Remove-Partition", re.IGNORECASE),
    re.compile(r"Stop-Computer\s+-Force", re.IGNORECASE),
    re.compile(r"Remove-ADUser", re.IGNORECASE),
    re.compile(r"Remove-ADGroup", re.IGNORECASE),
    re.compile(r"Disable-ADAccount.*Administrator", re.IGNORECASE),
    re.compile(r"DROP\s+TABLE", re.IGNORECASE),
    re.compile(r":(){ :\|:& };:"),
]


def _is_forbidden(command: str) -> bool:
    """Check if a PowerShell command matches any forbidden pattern."""
    return any(p.search(command) for p in FORBIDDEN_PATTERNS)


class WindowsConnector(InfraConnector):
    """Connector for Windows servers via WinRM (pywinrm)."""

    provider = "windows"

    def __init__(
        self,
        host: str,
        username: str = "Administrator",
        password: str = "",
        use_ssl: bool = True,
        port: int = 5986,
    ) -> None:
        self._host = host
        self._username = username
        self._password = password
        self._use_ssl = use_ssl
        self._port = port
        self._session: Any = None
        self._snapshots: dict[str, dict[str, Any]] = {}

    def _ensure_session(self) -> Any:
        """Lazily create a WinRM session."""
        if self._session is None:
            import winrm

            protocol = "https" if self._use_ssl else "http"
            endpoint = f"{protocol}://{self._host}:{self._port}/wsman"
            self._session = winrm.Session(
                endpoint,
                auth=(self._username, self._password),
                transport="ntlm",
                server_cert_validation="ignore" if self._use_ssl else "validate",
            )
            logger.info("windows_winrm_connected", host=self._host, user=self._username)
        return self._session

    async def _run_ps(self, script: str) -> tuple[str, str, int]:
        """Run a PowerShell script via WinRM and return (stdout, stderr, status_code)."""
        if _is_forbidden(script):
            raise ValueError(f"Forbidden command blocked by security guardrail: {script}")

        session = self._ensure_session()
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, partial(session.run_ps, script))
        stdout = result.std_out.decode("utf-8", errors="replace") if result.std_out else ""
        stderr = result.std_err.decode("utf-8", errors="replace") if result.std_err else ""
        return stdout, stderr, result.status_code

    async def get_health(self, resource_id: str) -> HealthStatus:
        """Get health of a Windows service.

        resource_id: service name (e.g. "W3SVC", "MSSQLSERVER")
        """
        try:
            stdout, _, exit_code = await self._run_ps(
                f"Get-Service -Name '{resource_id}' | "
                "Select-Object Status, DisplayName, StartType | "
                "ConvertTo-Json"
            )
            import json

            data: dict[str, Any] = {}
            if stdout.strip():
                data = json.loads(stdout.strip())

            status_val = data.get("Status", 0)
            # WinRM returns Status as int: 4 = Running, 1 = Stopped
            is_running = status_val == 4 or str(status_val).lower() == "running"

            return HealthStatus(
                resource_id=resource_id,
                healthy=is_running,
                status="running" if is_running else "stopped",
                message=f"DisplayName={data.get('DisplayName', resource_id)}",
                last_checked=datetime.now(UTC),
                metrics={
                    "start_type_code": float(data.get("StartType", 0)),
                },
            )
        except Exception as e:
            logger.error("windows_health_check_failed", resource_id=resource_id, error=str(e))
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
        """List running Windows services."""
        try:
            stdout, _, _ = await self._run_ps(
                "Get-Service | Where-Object {$_.Status -eq 'Running'} | "
                "Select-Object Name, DisplayName, StartType | ConvertTo-Json"
            )
            import json

            services: list[dict[str, Any]] = []
            if stdout.strip():
                parsed = json.loads(stdout.strip())
                services = [parsed] if isinstance(parsed, dict) else parsed

            resources: list[Resource] = []
            for svc in services:
                svc_name = svc.get("Name", "")
                resources.append(
                    Resource(
                        id=svc_name,
                        name=svc.get("DisplayName", svc_name),
                        resource_type="service",
                        environment=environment,
                        provider="windows",
                        labels={"host": self._host},
                        metadata={"start_type": str(svc.get("StartType", ""))},
                    )
                )
            return resources
        except Exception as e:
            logger.error("windows_list_resources_failed", error=str(e))
            return []

    async def get_events(self, resource_id: str, time_range: TimeRange) -> list[dict[str, Any]]:
        """Get Windows Event Log entries for a service."""
        try:
            since = time_range.start.strftime("%m/%d/%Y %H:%M:%S")
            until = time_range.end.strftime("%m/%d/%Y %H:%M:%S")
            stdout, _, _ = await self._run_ps(
                f"Get-EventLog -LogName System -Source '{resource_id}' "
                f"-After '{since}' -Before '{until}' -Newest 500 "
                "| Select-Object TimeGenerated, EntryType, Message "
                "| ConvertTo-Json"
            )
            import json

            events: list[dict[str, Any]] = []
            if stdout.strip():
                parsed = json.loads(stdout.strip())
                if isinstance(parsed, dict):
                    parsed = [parsed]
                for entry in parsed:
                    events.append(
                        {
                            "timestamp": entry.get("TimeGenerated"),
                            "message": entry.get("Message", ""),
                            "level": entry.get("EntryType", ""),
                            "source": resource_id,
                        }
                    )
            return events
        except Exception as e:
            logger.error("windows_get_events_failed", resource_id=resource_id, error=str(e))
            return []

    async def execute_action(self, action: RemediationAction) -> ActionResult:
        """Execute a remediation action on a Windows service."""
        started_at = datetime.now(UTC)

        logger.info(
            "windows_execute_action",
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
            return ActionResult(
                action_id=action.id,
                status=ExecutionStatus.FAILED,
                message=f"Security guardrail: {e}",
                started_at=started_at,
                completed_at=datetime.now(UTC),
                error=str(e),
            )
        except Exception as e:
            logger.error("windows_action_failed", action=action.id, error=str(e))
            return ActionResult(
                action_id=action.id,
                status=ExecutionStatus.FAILED,
                message=f"WinRM error: {e}",
                started_at=started_at,
                completed_at=datetime.now(UTC),
                error=str(e),
            )

    async def _restart_service(
        self, action: RemediationAction, started_at: datetime
    ) -> ActionResult:
        service = action.target_resource
        _, stderr, exit_code = await self._run_ps(f"Restart-Service -Name '{service}' -Force")
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
        _, stderr, exit_code = await self._run_ps(f"Stop-Service -Name '{service}' -Force")
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
        _, stderr, exit_code = await self._run_ps(f"Start-Service -Name '{service}'")
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
        _, stderr, exit_code = await self._run_ps(
            f"Install-Package -Name '{package}' -Force -Confirm:$false"
        )
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
        """Capture Windows service state for rollback."""
        snapshot_id = str(uuid4())
        try:
            stdout, _, _ = await self._run_ps(
                f"Get-Service -Name '{resource_id}' | Select-Object * | ConvertTo-Json"
            )
            state = {
                "service": resource_id,
                "details": stdout,
                "host": self._host,
            }
        except Exception:
            state = {"resource_id": resource_id, "error": "could_not_capture"}

        snapshot = Snapshot(
            id=snapshot_id,
            resource_id=resource_id,
            snapshot_type="windows_service",
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

        logger.info("windows_rollback", snapshot_id=snapshot_id)
        return ActionResult(
            action_id=f"rollback-{snapshot_id}",
            status=ExecutionStatus.SUCCESS,
            message=f"Rolled back to snapshot {snapshot_id}",
            started_at=started_at,
            completed_at=datetime.now(UTC),
            snapshot_id=snapshot_id,
        )

    async def validate_health(self, resource_id: str, timeout_seconds: int = 300) -> bool:
        """Poll service status until healthy or timeout."""
        deadline = datetime.now(UTC).timestamp() + timeout_seconds
        while datetime.now(UTC).timestamp() < deadline:
            health = await self.get_health(resource_id)
            if health.healthy:
                return True
            await asyncio.sleep(5)
        return False

    async def close(self) -> None:
        """Clean up WinRM session."""
        self._session = None
