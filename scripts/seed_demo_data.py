"""Seed the database with demo data for showcasing ShieldOps."""

import argparse
import asyncio
import os
import sys
from datetime import UTC, datetime, timedelta


async def seed(database_url: str) -> None:
    """Insert demo data into all ShieldOps tables."""

    # ------------------------------------------------------------------
    # Lazy imports so the script fails fast with a clear message if the
    # shieldops package is not installed or DB tables are missing.
    # ------------------------------------------------------------------
    try:
        from sqlalchemy import select
        from sqlalchemy.ext.asyncio import AsyncSession

        from shieldops.api.auth.service import hash_password
        from shieldops.db.models import (
            AgentRegistration,
            InvestigationRecord,
            RemediationRecord,
            SecurityScanRecord,
            UserRecord,
        )
        from shieldops.db.session import create_async_engine, get_session_factory
    except ImportError as exc:
        print(f"[ERROR] Failed to import ShieldOps modules: {exc}")
        print("Make sure the shieldops package is installed (pip install -e .).")
        sys.exit(1)

    engine = create_async_engine(database_url)
    factory = get_session_factory()

    # ------------------------------------------------------------------
    # Helper: check if a row already exists by primary key
    # ------------------------------------------------------------------
    async def _exists(session: AsyncSession, model: type, pk: str) -> bool:
        return (await session.get(model, pk)) is not None

    now = datetime.now(UTC)

    # ==================================================================
    # 1. Users
    # ==================================================================
    users = [
        {
            "id": "usr-demo-admin01",
            "email": "admin@shieldops.dev",
            "name": "Demo Admin",
            "password": "shieldops-admin",
            "role": "admin",
        },
        {
            "id": "usr-demo-oper01",
            "email": "operator@shieldops.dev",
            "name": "Demo Operator",
            "password": "shieldops-operator",
            "role": "operator",
        },
        {
            "id": "usr-demo-view01",
            "email": "viewer@shieldops.dev",
            "name": "Demo Viewer",
            "password": "shieldops-viewer",
            "role": "viewer",
        },
    ]

    async with factory() as session:
        for u in users:
            if await _exists(session, UserRecord, u["id"]):
                print(f"  [SKIP] User {u['email']} already exists")
                continue
            # Also skip if the email is already taken (different id)
            existing = await session.execute(
                select(UserRecord).where(UserRecord.email == u["email"])
            )
            if existing.scalar_one_or_none() is not None:
                print(f"  [SKIP] User {u['email']} already exists (different id)")
                continue
            record = UserRecord(
                id=u["id"],
                email=u["email"],
                name=u["name"],
                password_hash=hash_password(u["password"]),
                role=u["role"],
            )
            session.add(record)
            print(f"  [OK]   User {u['email']} ({u['role']})")
        await session.commit()
    print("[1/5] Users seeded")

    # ==================================================================
    # 2. Agent Registrations
    # ==================================================================
    agent_types = [
        "investigation",
        "remediation",
        "security",
        "learning",
        "supervisor",
        "orchestrator",
    ]
    agents = [
        {
            "id": f"agt-demo-{atype[:6]}{idx:02d}",
            "agent_type": atype,
            "environment": "production",
            "status": "idle",
            "config": {"version": "0.1.0", "max_concurrency": 5},
            "last_heartbeat": now - timedelta(seconds=30 * (idx + 1)),
        }
        for idx, atype in enumerate(agent_types)
    ]

    async with factory() as session:
        for a in agents:
            if await _exists(session, AgentRegistration, a["id"]):
                print(f"  [SKIP] Agent {a['agent_type']} already exists")
                continue
            record = AgentRegistration(**a)
            session.add(record)
            print(f"  [OK]   Agent {a['agent_type']}")
        await session.commit()
    print("[2/5] Agent registrations seeded")

    # ==================================================================
    # 3. Investigations (10 records)
    # ==================================================================
    investigations = [
        # --- completed (3) ---
        {
            "id": "inv-demo-001",
            "alert_id": "alert-k8s-001",
            "alert_name": "KubePodCrashLooping",
            "severity": "critical",
            "status": "completed",
            "confidence": 0.92,
            "hypotheses": [
                {"hypothesis": "OOM kill due to memory leak in worker process", "confidence": 0.92}
            ],
            "alert_context": {
                "alert_name": "KubePodCrashLooping",
                "severity": "critical",
                "resource": "default/api-server",
            },
            "log_findings": [{"source": "kubelet", "message": "OOMKilled container api-server"}],
            "metric_anomalies": [
                {"metric": "container_memory_working_set_bytes", "deviation": 3.2}
            ],
            "recommended_action": {
                "action_type": "restart_pod",
                "target_resource": "default/api-server",
                "confidence": 0.92,
            },
            "duration_ms": 12340,
            "created_at": now - timedelta(hours=6),
        },
        {
            "id": "inv-demo-002",
            "alert_id": "alert-cpu-002",
            "alert_name": "HighCPUUsage",
            "severity": "high",
            "status": "completed",
            "confidence": 0.87,
            "hypotheses": [
                {"hypothesis": "Runaway goroutine in payment service", "confidence": 0.87}
            ],
            "alert_context": {
                "alert_name": "HighCPUUsage",
                "severity": "high",
                "resource": "production/payment-svc",
            },
            "log_findings": [
                {"source": "application", "message": "goroutine count exceeded 10000"}
            ],
            "metric_anomalies": [{"metric": "node_cpu_seconds_total", "deviation": 4.1}],
            "recommended_action": {
                "action_type": "restart_pod",
                "target_resource": "production/payment-svc",
                "confidence": 0.87,
            },
            "duration_ms": 8920,
            "created_at": now - timedelta(hours=12),
        },
        {
            "id": "inv-demo-003",
            "alert_id": "alert-ssl-003",
            "alert_name": "SSLCertExpiring",
            "severity": "warning",
            "status": "completed",
            "confidence": 0.95,
            "hypotheses": [
                {
                    "hypothesis": "TLS certificate for api.prod expires in 7 days",
                    "confidence": 0.95,
                }
            ],
            "alert_context": {
                "alert_name": "SSLCertExpiring",
                "severity": "warning",
                "resource": "production/ingress-api",
            },
            "log_findings": [],
            "metric_anomalies": [],
            "recommended_action": {
                "action_type": "rotate_credentials",
                "target_resource": "production/ingress-api",
                "confidence": 0.95,
            },
            "duration_ms": 4100,
            "created_at": now - timedelta(hours=24),
        },
        # --- in_progress (2) ---
        {
            "id": "inv-demo-004",
            "alert_id": "alert-mem-004",
            "alert_name": "MemoryPressure",
            "severity": "high",
            "status": "in_progress",
            "confidence": 0.45,
            "hypotheses": [
                {"hypothesis": "Possible memory leak in cache layer", "confidence": 0.45}
            ],
            "alert_context": {
                "alert_name": "MemoryPressure",
                "severity": "high",
                "resource": "production/worker-pool",
            },
            "log_findings": [
                {"source": "system", "message": "oom_score_adj approaching threshold"}
            ],
            "metric_anomalies": [{"metric": "node_memory_MemAvailable_bytes", "deviation": 2.8}],
            "duration_ms": 0,
            "created_at": now - timedelta(minutes=15),
        },
        {
            "id": "inv-demo-005",
            "alert_id": "alert-net-005",
            "alert_name": "NetworkLatency",
            "severity": "warning",
            "status": "in_progress",
            "confidence": 0.30,
            "hypotheses": [
                {
                    "hypothesis": "Cross-AZ traffic spike due to misconfigured service mesh",
                    "confidence": 0.30,
                }
            ],
            "alert_context": {
                "alert_name": "NetworkLatency",
                "severity": "warning",
                "resource": "production/service-mesh",
            },
            "log_findings": [],
            "metric_anomalies": [
                {"metric": "istio_request_duration_milliseconds", "deviation": 2.1}
            ],
            "duration_ms": 0,
            "created_at": now - timedelta(minutes=8),
        },
        # --- pending (3) ---
        {
            "id": "inv-demo-006",
            "alert_id": "alert-disk-006",
            "alert_name": "DiskFull",
            "severity": "critical",
            "status": "pending",
            "confidence": 0.0,
            "hypotheses": [],
            "alert_context": {
                "alert_name": "DiskFull",
                "severity": "critical",
                "resource": "staging/db-replica",
            },
            "log_findings": [],
            "metric_anomalies": [],
            "duration_ms": 0,
            "created_at": now - timedelta(minutes=3),
        },
        {
            "id": "inv-demo-007",
            "alert_id": "alert-pod-007",
            "alert_name": "KubePodCrashLooping",
            "severity": "high",
            "status": "pending",
            "confidence": 0.0,
            "hypotheses": [],
            "alert_context": {
                "alert_name": "KubePodCrashLooping",
                "severity": "high",
                "resource": "staging/auth-service",
            },
            "log_findings": [],
            "metric_anomalies": [],
            "duration_ms": 0,
            "created_at": now - timedelta(minutes=2),
        },
        {
            "id": "inv-demo-008",
            "alert_id": "alert-node-008",
            "alert_name": "NodeNotReady",
            "severity": "critical",
            "status": "pending",
            "confidence": 0.0,
            "hypotheses": [],
            "alert_context": {
                "alert_name": "NodeNotReady",
                "severity": "critical",
                "resource": "production/node-pool-3",
            },
            "log_findings": [],
            "metric_anomalies": [],
            "duration_ms": 0,
            "created_at": now - timedelta(minutes=1),
        },
        # --- failed (2) ---
        {
            "id": "inv-demo-009",
            "alert_id": "alert-log-009",
            "alert_name": "ErrorRateSpike",
            "severity": "high",
            "status": "failed",
            "confidence": 0.0,
            "hypotheses": [],
            "alert_context": {
                "alert_name": "ErrorRateSpike",
                "severity": "high",
                "resource": "production/checkout-svc",
            },
            "log_findings": [],
            "metric_anomalies": [],
            "error": "Timeout: investigation exceeded 600s limit",
            "duration_ms": 600000,
            "created_at": now - timedelta(hours=3),
        },
        {
            "id": "inv-demo-010",
            "alert_id": "alert-conn-010",
            "alert_name": "DatabaseConnectionPoolExhausted",
            "severity": "critical",
            "status": "failed",
            "confidence": 0.12,
            "hypotheses": [
                {"hypothesis": "Connection leak in ORM session management", "confidence": 0.12}
            ],
            "alert_context": {
                "alert_name": "DatabaseConnectionPoolExhausted",
                "severity": "critical",
                "resource": "production/primary-db",
            },
            "log_findings": [{"source": "pgbouncer", "message": "no more connections allowed"}],
            "metric_anomalies": [],
            "error": "LLM provider returned 503 during hypothesis generation",
            "duration_ms": 45200,
            "created_at": now - timedelta(hours=8),
        },
    ]

    async with factory() as session:
        for inv in investigations:
            if await _exists(session, InvestigationRecord, inv["id"]):
                print(f"  [SKIP] Investigation {inv['id']} already exists")
                continue
            record = InvestigationRecord(
                id=inv["id"],
                alert_id=inv["alert_id"],
                alert_name=inv["alert_name"],
                severity=inv["severity"],
                status=inv["status"],
                confidence=inv["confidence"],
                hypotheses=inv.get("hypotheses", []),
                reasoning_chain=[],
                alert_context=inv.get("alert_context", {}),
                log_findings=inv.get("log_findings", []),
                metric_anomalies=inv.get("metric_anomalies", []),
                recommended_action=inv.get("recommended_action"),
                error=inv.get("error"),
                duration_ms=inv.get("duration_ms", 0),
            )
            session.add(record)
            print(f"  [OK]   Investigation {inv['id']} ({inv['alert_name']})")
        await session.commit()
    print("[3/5] Investigations seeded")

    # ==================================================================
    # 4. Remediations (8 records)
    # ==================================================================
    remediations = [
        # completed (3)
        {
            "id": "rem-demo-001",
            "action_type": "restart_pod",
            "target_resource": "default/api-server",
            "environment": "production",
            "risk_level": "low",
            "status": "completed",
            "validation_passed": True,
            "investigation_id": "inv-demo-001",
            "action_data": {
                "action_type": "restart_pod",
                "target_resource": "default/api-server",
                "namespace": "default",
            },
            "execution_result": {"success": True, "message": "Pod restarted successfully"},
            "duration_ms": 3200,
            "created_at": now - timedelta(hours=5),
        },
        {
            "id": "rem-demo-002",
            "action_type": "restart_pod",
            "target_resource": "production/payment-svc",
            "environment": "production",
            "risk_level": "medium",
            "status": "completed",
            "validation_passed": True,
            "investigation_id": "inv-demo-002",
            "action_data": {
                "action_type": "restart_pod",
                "target_resource": "production/payment-svc",
                "namespace": "production",
            },
            "execution_result": {"success": True, "message": "Pod restarted, CPU normalized"},
            "duration_ms": 4800,
            "created_at": now - timedelta(hours=11),
        },
        {
            "id": "rem-demo-003",
            "action_type": "scale_deployment",
            "target_resource": "production/worker-pool",
            "environment": "production",
            "risk_level": "medium",
            "status": "completed",
            "validation_passed": True,
            "investigation_id": None,
            "action_data": {
                "action_type": "scale_deployment",
                "target_resource": "production/worker-pool",
                "replicas": 5,
            },
            "execution_result": {"success": True, "message": "Scaled to 5 replicas"},
            "duration_ms": 8900,
            "created_at": now - timedelta(hours=18),
        },
        # executing (1)
        {
            "id": "rem-demo-004",
            "action_type": "rollback_deployment",
            "target_resource": "staging/auth-service",
            "environment": "staging",
            "risk_level": "high",
            "status": "executing",
            "validation_passed": True,
            "investigation_id": "inv-demo-007",
            "action_data": {
                "action_type": "rollback_deployment",
                "target_resource": "staging/auth-service",
                "revision": "v2.3.1",
            },
            "duration_ms": 0,
            "created_at": now - timedelta(minutes=5),
        },
        # pending_approval (2)
        {
            "id": "rem-demo-005",
            "action_type": "rotate_credentials",
            "target_resource": "production/ingress-api",
            "environment": "production",
            "risk_level": "high",
            "status": "pending_approval",
            "validation_passed": None,
            "investigation_id": "inv-demo-003",
            "action_data": {
                "action_type": "rotate_credentials",
                "target_resource": "production/ingress-api",
                "credential_type": "tls_certificate",
            },
            "duration_ms": 0,
            "created_at": now - timedelta(hours=23),
        },
        {
            "id": "rem-demo-006",
            "action_type": "scale_deployment",
            "target_resource": "production/primary-db",
            "environment": "production",
            "risk_level": "critical",
            "status": "pending_approval",
            "validation_passed": None,
            "investigation_id": "inv-demo-010",
            "action_data": {
                "action_type": "scale_deployment",
                "target_resource": "production/primary-db",
                "replicas": 3,
            },
            "duration_ms": 0,
            "created_at": now - timedelta(hours=7),
        },
        # failed (1)
        {
            "id": "rem-demo-007",
            "action_type": "restart_pod",
            "target_resource": "production/checkout-svc",
            "environment": "production",
            "risk_level": "medium",
            "status": "failed",
            "validation_passed": False,
            "investigation_id": "inv-demo-009",
            "action_data": {
                "action_type": "restart_pod",
                "target_resource": "production/checkout-svc",
            },
            "execution_result": {"success": False, "message": "Pod stuck in CrashBackOffLoop"},
            "error": "Pre-execution validation failed: blast-radius limit exceeded",
            "duration_ms": 1200,
            "created_at": now - timedelta(hours=2, minutes=45),
        },
        # rolled_back (1)
        {
            "id": "rem-demo-008",
            "action_type": "rollback_deployment",
            "target_resource": "production/search-svc",
            "environment": "production",
            "risk_level": "high",
            "status": "rolled_back",
            "validation_passed": True,
            "investigation_id": None,
            "action_data": {
                "action_type": "rollback_deployment",
                "target_resource": "production/search-svc",
                "revision": "v1.8.0",
            },
            "execution_result": {
                "success": False,
                "message": "Deployment health check failed post-rollout",
            },
            "snapshot_data": {
                "previous_replicas": 3,
                "previous_image": "search-svc:v1.7.2",
            },
            "duration_ms": 15400,
            "created_at": now - timedelta(days=1, hours=4),
        },
    ]

    async with factory() as session:
        for rem in remediations:
            if await _exists(session, RemediationRecord, rem["id"]):
                print(f"  [SKIP] Remediation {rem['id']} already exists")
                continue
            record = RemediationRecord(
                id=rem["id"],
                action_type=rem["action_type"],
                target_resource=rem["target_resource"],
                environment=rem["environment"],
                risk_level=rem["risk_level"],
                status=rem["status"],
                validation_passed=rem.get("validation_passed"),
                reasoning_chain=[],
                action_data=rem.get("action_data", {}),
                execution_result=rem.get("execution_result"),
                snapshot_data=rem.get("snapshot_data"),
                investigation_id=rem.get("investigation_id"),
                error=rem.get("error"),
                duration_ms=rem.get("duration_ms", 0),
            )
            session.add(record)
            print(f"  [OK]   Remediation {rem['id']} ({rem['action_type']})")
        await session.commit()
    print("[4/5] Remediations seeded")

    # ==================================================================
    # 5. Security Scans (3 records)
    # ==================================================================
    security_scans = [
        # Completed vulnerability scan with findings
        {
            "id": "sec-demo-001",
            "scan_type": "vulnerability",
            "environment": "production",
            "status": "completed",
            "cve_findings": [
                {
                    "cve_id": "CVE-2024-32002",
                    "severity": "critical",
                    "package": "git",
                    "fixed_version": "2.45.1",
                    "description": "Git recursive clone RCE on case-insensitive filesystems",
                },
                {
                    "cve_id": "CVE-2024-29018",
                    "severity": "high",
                    "package": "docker",
                    "fixed_version": "26.0.1",
                    "description": "Moby external DNS requests from internal networks",
                },
                {
                    "cve_id": "CVE-2024-21626",
                    "severity": "critical",
                    "package": "runc",
                    "fixed_version": "1.1.12",
                    "description": "Leaky file descriptor in runc allowing container escape",
                },
            ],
            "critical_cve_count": 2,
            "credential_statuses": [],
            "compliance_controls": [],
            "compliance_score": 0.0,
            "patch_results": [
                {"cve_id": "CVE-2024-32002", "status": "patched", "package": "git"},
            ],
            "rotation_results": [],
            "patches_applied": 1,
            "credentials_rotated": 0,
            "posture_data": {
                "overall_risk": "high",
                "open_criticals": 1,
                "open_highs": 1,
                "scan_coverage": 0.94,
            },
            "duration_ms": 34500,
            "created_at": now - timedelta(hours=4),
        },
        # Completed credential scan
        {
            "id": "sec-demo-002",
            "scan_type": "credential",
            "environment": "production",
            "status": "completed",
            "cve_findings": [],
            "critical_cve_count": 0,
            "credential_statuses": [
                {
                    "credential_id": "db-prod-password",
                    "type": "database",
                    "age_days": 45,
                    "status": "rotation_due",
                    "last_rotated": (now - timedelta(days=45)).isoformat(),
                },
                {
                    "credential_id": "api-key-external",
                    "type": "api_key",
                    "age_days": 12,
                    "status": "healthy",
                    "last_rotated": (now - timedelta(days=12)).isoformat(),
                },
                {
                    "credential_id": "tls-cert-api",
                    "type": "tls_certificate",
                    "age_days": 83,
                    "status": "expiring_soon",
                    "expires_in_days": 7,
                },
            ],
            "compliance_controls": [],
            "compliance_score": 0.0,
            "patch_results": [],
            "rotation_results": [
                {"credential_id": "db-prod-password", "status": "rotated"},
            ],
            "patches_applied": 0,
            "credentials_rotated": 1,
            "posture_data": {
                "credentials_total": 3,
                "credentials_healthy": 1,
                "credentials_due_rotation": 1,
                "credentials_expiring": 1,
            },
            "duration_ms": 18200,
            "created_at": now - timedelta(hours=2),
        },
        # Running compliance scan
        {
            "id": "sec-demo-003",
            "scan_type": "compliance",
            "environment": "production",
            "status": "running",
            "cve_findings": [],
            "critical_cve_count": 0,
            "credential_statuses": [],
            "compliance_controls": [
                {
                    "control_id": "CIS-K8S-1.1.1",
                    "description": "Ensure API server --anonymous-auth is set to false",
                    "status": "pass",
                },
                {
                    "control_id": "CIS-K8S-1.2.1",
                    "description": "Ensure RBAC is enabled",
                    "status": "pass",
                },
                {
                    "control_id": "CIS-K8S-5.1.1",
                    "description": "Ensure cluster-admin role is only used where required",
                    "status": "evaluating",
                },
            ],
            "compliance_score": 0.67,
            "patch_results": [],
            "rotation_results": [],
            "patches_applied": 0,
            "credentials_rotated": 0,
            "duration_ms": 0,
            "created_at": now - timedelta(minutes=10),
        },
    ]

    async with factory() as session:
        for scan in security_scans:
            if await _exists(session, SecurityScanRecord, scan["id"]):
                print(f"  [SKIP] Security scan {scan['id']} already exists")
                continue
            record = SecurityScanRecord(
                id=scan["id"],
                scan_type=scan["scan_type"],
                environment=scan["environment"],
                status=scan["status"],
                cve_findings=scan.get("cve_findings", []),
                critical_cve_count=scan.get("critical_cve_count", 0),
                credential_statuses=scan.get("credential_statuses", []),
                compliance_controls=scan.get("compliance_controls", []),
                compliance_score=scan.get("compliance_score", 0.0),
                patch_results=scan.get("patch_results", []),
                rotation_results=scan.get("rotation_results", []),
                patches_applied=scan.get("patches_applied", 0),
                credentials_rotated=scan.get("credentials_rotated", 0),
                posture_data=scan.get("posture_data"),
                reasoning_chain=[],
                error=scan.get("error"),
                duration_ms=scan.get("duration_ms", 0),
            )
            session.add(record)
            print(f"  [OK]   Security scan {scan['id']} ({scan['scan_type']})")
        await session.commit()
    print("[5/5] Security scans seeded")

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------
    await engine.dispose()
    print("\nDone. Demo data seeded successfully.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the ShieldOps database with demo data.")
    parser.add_argument(
        "--database-url",
        default=os.environ.get(
            "SHIELDOPS_DATABASE_URL",
            "postgresql+asyncpg://shieldops:shieldops@localhost:5432/shieldops",
        ),
        help="Async SQLAlchemy database URL (default: SHIELDOPS_DATABASE_URL env var)",
    )
    args = parser.parse_args()

    print(f"Seeding demo data into: {args.database_url.split('@')[-1]}")
    print("=" * 60)

    try:
        asyncio.run(seed(args.database_url))
    except Exception as exc:
        print(f"\n[ERROR] Seed failed: {exc}")
        print(
            "Hint: Make sure the database is running and migrations have been applied "
            "(alembic upgrade head)."
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
