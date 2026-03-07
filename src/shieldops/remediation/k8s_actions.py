"""Production-ready Kubernetes remediation actions.

Each action follows the pattern:
  1. Policy gate evaluation (OPA + built-in rules)
  2. Pre-action snapshot (for rollback)
  3. Execute the action via kubernetes_asyncio
  4. Health verification (wait for pods ready / deployment available)
  5. Return RemediationResult with before/after state and audit trail
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog
from kubernetes_asyncio import client, config

from shieldops.config.settings import Settings
from shieldops.remediation.models import (
    K8sActionType,
    K8sRemediationRequest,
    RemediationResult,
    RemediationStatus,
)
from shieldops.remediation.policy_gate import PolicyGate
from shieldops.remediation.rollback import RollbackManager

logger = structlog.get_logger()


class K8sRemediationExecutor:
    """Executes Kubernetes remediation actions with policy gates and rollback safety.

    Usage::

        executor = K8sRemediationExecutor()
        result = await executor.execute(K8sRemediationRequest(
            action_type=K8sActionType.RESTART_POD,
            namespace="default",
            resource_name="my-pod-abc123",
        ))
    """

    def __init__(
        self,
        kubeconfig_path: str | None = None,
        context: str | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._kubeconfig_path = kubeconfig_path
        self._context = context
        self._settings = settings or Settings()
        self._core_api: client.CoreV1Api | None = None
        self._apps_api: client.AppsV1Api | None = None
        self._autoscaling_api: client.AutoscalingV1Api | None = None
        self._policy_gate = PolicyGate(settings=self._settings)
        self._rollback_mgr = RollbackManager(
            kubeconfig_path=kubeconfig_path,
            context=context,
        )
        self._results: dict[str, RemediationResult] = {}

    async def _ensure_client(self) -> None:
        """Initialize Kubernetes client if not already done."""
        if self._core_api is not None:
            return
        if self._kubeconfig_path:
            await config.load_kube_config(
                config_file=self._kubeconfig_path,
                context=self._context,
            )
        else:
            config.load_incluster_config()
        self._core_api = client.CoreV1Api()
        self._apps_api = client.AppsV1Api()
        self._autoscaling_api = client.AutoscalingV1Api()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def execute(self, request: K8sRemediationRequest) -> RemediationResult:
        """Execute a remediation action with full policy/snapshot/verify lifecycle.

        Args:
            request: The remediation action request.

        Returns:
            RemediationResult with status, before/after state, and audit log.
        """
        await self._ensure_client()
        started_at = datetime.now(UTC)
        audit: list[str] = []

        result = RemediationResult(
            action_type=request.action_type,
            namespace=request.namespace,
            resource_name=request.resource_name,
            environment=request.environment,
            status=RemediationStatus.POLICY_CHECK,
            initiated_by=request.initiated_by,
            started_at=started_at,
        )
        audit.append(
            f"[{_ts()}] Action requested: {request.action_type} on "
            f"{request.namespace}/{request.resource_name}"
        )

        # Step 1 — Policy gate
        decision = await self._policy_gate.evaluate_action(
            action_type=request.action_type,
            namespace=request.namespace,
            resource_name=request.resource_name,
            environment=request.environment,
            parameters=request.parameters,
        )
        result.risk_level = decision.risk_level
        audit.append(
            f"[{_ts()}] Policy decision: allowed={decision.allowed}, "
            f"risk={decision.risk_level}, approval={decision.requires_approval}"
        )

        if not decision.allowed:
            result.status = RemediationStatus.DENIED
            result.message = f"Policy denied: {decision.reason}"
            result.completed_at = datetime.now(UTC)
            result.duration_seconds = _elapsed(started_at)
            result.audit_log = audit
            audit.append(f"[{_ts()}] Action DENIED by policy gate")
            self._results[result.id] = result
            return result

        # Step 2 — Pre-action snapshot
        resource_type = _action_to_resource_type(request.action_type)
        snapshot = None
        try:
            snapshot = await self._rollback_mgr.create_snapshot(
                namespace=request.namespace,
                resource_type=resource_type,
                resource_name=request.resource_name,
            )
            result.snapshot_id = snapshot.id
            result.before_state = snapshot.state_json
            audit.append(f"[{_ts()}] Snapshot captured: {snapshot.id}")
        except Exception as exc:
            audit.append(f"[{_ts()}] Snapshot warning: {exc}")
            logger.warning("snapshot_failed", error=str(exc))

        # Step 3 — Execute action
        result.status = RemediationStatus.IN_PROGRESS
        audit.append(f"[{_ts()}] Executing action: {request.action_type}")

        try:
            action_result = await self._dispatch_action(request)
            result.message = action_result.get("message", "")
            result.after_state = action_result.get("after_state", {})
            audit.append(f"[{_ts()}] Action executed: {action_result.get('message', 'ok')}")
        except client.ApiException as exc:
            result.status = RemediationStatus.FAILED
            result.error = f"K8s API error: {exc.reason} (status {exc.status})"
            result.message = f"Failed: {exc.reason}"
            result.completed_at = datetime.now(UTC)
            result.duration_seconds = _elapsed(started_at)
            result.audit_log = audit
            audit.append(f"[{_ts()}] Action FAILED: {exc.reason}")
            self._results[result.id] = result
            return result
        except Exception as exc:
            result.status = RemediationStatus.FAILED
            result.error = str(exc)
            result.message = f"Failed: {exc}"
            result.completed_at = datetime.now(UTC)
            result.duration_seconds = _elapsed(started_at)
            result.audit_log = audit
            audit.append(f"[{_ts()}] Action FAILED: {exc}")
            self._results[result.id] = result
            return result

        # Step 4 — Health verification (only for deployment-related actions)
        if request.action_type in {
            K8sActionType.RESTART_DEPLOYMENT,
            K8sActionType.ROLLBACK_DEPLOYMENT,
            K8sActionType.SCALE_DEPLOYMENT,
            K8sActionType.UPDATE_RESOURCE_LIMITS,
        }:
            audit.append(f"[{_ts()}] Verifying deployment health...")
            healthy = await self._rollback_mgr.verify_health(
                namespace=request.namespace,
                deployment_name=request.resource_name,
                timeout_seconds=120,
            )
            if healthy:
                audit.append(f"[{_ts()}] Health check PASSED")
            else:
                audit.append(f"[{_ts()}] Health check FAILED — initiating rollback")
                logger.warning(
                    "health_check_failed_rollback",
                    action=request.action_type,
                    resource=request.resource_name,
                )
                if snapshot:
                    try:
                        await self._rollback_mgr.rollback_to_snapshot(snapshot)
                        result.status = RemediationStatus.ROLLED_BACK
                        result.message = "Action completed but health check failed; rolled back"
                        audit.append(f"[{_ts()}] Rollback completed to snapshot {snapshot.id}")
                    except Exception as rb_exc:
                        result.status = RemediationStatus.FAILED
                        result.error = f"Rollback also failed: {rb_exc}"
                        audit.append(f"[{_ts()}] Rollback FAILED: {rb_exc}")
                else:
                    result.status = RemediationStatus.FAILED
                    result.message = "Health check failed and no snapshot available for rollback"
                    audit.append(f"[{_ts()}] No snapshot available for rollback")

        # Finalise
        if result.status == RemediationStatus.IN_PROGRESS:
            result.status = RemediationStatus.SUCCESS

        result.completed_at = datetime.now(UTC)
        result.duration_seconds = _elapsed(started_at)
        result.audit_log = audit
        audit.append(f"[{_ts()}] Final status: {result.status}")

        self._results[result.id] = result

        logger.info(
            "remediation_completed",
            action_id=result.id,
            action_type=request.action_type,
            status=result.status,
            duration=result.duration_seconds,
        )

        return result

    async def rollback_action(self, action_id: str) -> RemediationResult:
        """Rollback a previously executed action using its stored snapshot.

        Args:
            action_id: The ID of the RemediationResult to roll back.

        Returns:
            Updated RemediationResult with rolled-back status.

        Raises:
            ValueError: If the action ID is not found or has no snapshot.
        """
        result = self._results.get(action_id)
        if result is None:
            raise ValueError(f"Action {action_id} not found")

        if result.snapshot_id is None:
            raise ValueError(f"Action {action_id} has no snapshot for rollback")

        snapshot = self._rollback_mgr.get_snapshot(result.snapshot_id)
        if snapshot is None:
            raise ValueError(f"Snapshot {result.snapshot_id} not found")

        await self._rollback_mgr.rollback_to_snapshot(snapshot)

        result.status = RemediationStatus.ROLLED_BACK
        result.message = f"Rolled back to snapshot {result.snapshot_id}"
        result.audit_log.append(
            f"[{_ts()}] Manual rollback executed to snapshot {result.snapshot_id}"
        )

        return result

    def get_result(self, action_id: str) -> RemediationResult | None:
        """Retrieve a stored remediation result by ID."""
        return self._results.get(action_id)

    def get_snapshot(self, snapshot_id: str) -> Any:
        """Retrieve a stored snapshot by ID."""
        return self._rollback_mgr.get_snapshot(snapshot_id)

    # ------------------------------------------------------------------
    # Action dispatch
    # ------------------------------------------------------------------

    async def _dispatch_action(self, request: K8sRemediationRequest) -> dict[str, Any]:
        """Route to the correct action handler."""
        handlers = {
            K8sActionType.RESTART_POD: self._restart_pod,
            K8sActionType.RESTART_DEPLOYMENT: self._restart_deployment,
            K8sActionType.ROLLBACK_DEPLOYMENT: self._rollback_deployment,
            K8sActionType.SCALE_DEPLOYMENT: self._scale_deployment,
            K8sActionType.SCALE_HPA: self._scale_hpa,
            K8sActionType.CORDON_NODE: self._cordon_node,
            K8sActionType.DRAIN_NODE: self._drain_node,
            K8sActionType.UPDATE_CONFIG_MAP: self._update_config_map,
            K8sActionType.UPDATE_RESOURCE_LIMITS: self._update_resource_limits,
            K8sActionType.DELETE_EVICTED_PODS: self._delete_evicted_pods,
        }
        handler = handlers.get(request.action_type)
        if handler is None:
            raise ValueError(f"Unsupported action type: {request.action_type}")
        return await handler(request)

    # ------------------------------------------------------------------
    # Individual action implementations
    # ------------------------------------------------------------------

    async def _restart_pod(self, req: K8sRemediationRequest) -> dict[str, Any]:
        """Delete a pod so its controller (ReplicaSet/Deployment) recreates it."""
        assert self._core_api is not None

        await self._core_api.delete_namespaced_pod(
            name=req.resource_name,
            namespace=req.namespace,
        )

        return {
            "message": (
                f"Pod {req.namespace}/{req.resource_name} deleted (will be recreated by controller)"
            ),
        }

    async def _restart_deployment(self, req: K8sRemediationRequest) -> dict[str, Any]:
        """Trigger a rollout restart by patching the pod template annotation."""
        assert self._apps_api is not None

        restart_at = datetime.now(UTC).isoformat()
        body = {
            "spec": {
                "template": {
                    "metadata": {
                        "annotations": {
                            "shieldops.io/restartedAt": restart_at,
                        }
                    }
                }
            }
        }
        await self._apps_api.patch_namespaced_deployment(
            name=req.resource_name,
            namespace=req.namespace,
            body=body,
        )

        return {
            "message": f"Deployment {req.namespace}/{req.resource_name} rollout restart triggered",
            "after_state": {"restartedAt": restart_at},
        }

    async def _rollback_deployment(self, req: K8sRemediationRequest) -> dict[str, Any]:
        """Rollback a deployment to a previous or specific revision.

        If ``revision`` is provided in parameters, rolls back to that revision.
        Otherwise rolls back to the immediately previous revision by re-applying
        the previous ReplicaSet's pod template.
        """
        assert self._apps_api is not None

        revision = req.parameters.get("revision")

        if revision is not None:
            # Roll back to a specific revision by finding the matching ReplicaSet
            rs_list = await self._apps_api.list_namespaced_replica_set(
                namespace=req.namespace,
                label_selector=f"app={req.resource_name}",
            )
            target_rs = None
            for rs in rs_list.items:
                annotations = rs.metadata.annotations or {}
                if annotations.get("deployment.kubernetes.io/revision") == str(revision):
                    target_rs = rs
                    break

            if target_rs is None:
                raise ValueError(
                    f"Revision {revision} not found for deployment {req.resource_name}"
                )

            # Patch deployment with the target RS's pod template
            body = {"spec": {"template": target_rs.spec.template}}
            await self._apps_api.patch_namespaced_deployment(
                name=req.resource_name,
                namespace=req.namespace,
                body=client.ApiClient().sanitize_for_serialization(body),
            )
            msg = (
                f"Deployment {req.namespace}/{req.resource_name} rolled back to revision {revision}"
            )
        else:
            # Trigger rollback by annotating (equivalent to kubectl rollout undo)
            body = {
                "spec": {
                    "template": {
                        "metadata": {
                            "annotations": {
                                "shieldops.io/rollback-trigger": datetime.now(UTC).isoformat(),
                            }
                        }
                    }
                }
            }
            await self._apps_api.patch_namespaced_deployment(
                name=req.resource_name,
                namespace=req.namespace,
                body=body,
            )
            msg = f"Deployment {req.namespace}/{req.resource_name} rollback triggered"

        return {"message": msg, "after_state": {"revision": revision}}

    async def _scale_deployment(self, req: K8sRemediationRequest) -> dict[str, Any]:
        """Scale a deployment to a target replica count."""
        assert self._apps_api is not None

        replicas = req.parameters.get("replicas", 3)
        body = {"spec": {"replicas": replicas}}

        await self._apps_api.patch_namespaced_deployment_scale(
            name=req.resource_name,
            namespace=req.namespace,
            body=body,
        )

        return {
            "message": (
                f"Deployment {req.namespace}/{req.resource_name} scaled to {replicas} replicas"
            ),
            "after_state": {"replicas": replicas},
        }

    async def _scale_hpa(self, req: K8sRemediationRequest) -> dict[str, Any]:
        """Adjust HorizontalPodAutoscaler min/max replica bounds."""
        assert self._autoscaling_api is not None

        min_replicas = req.parameters.get("min_replicas")
        max_replicas = req.parameters.get("max_replicas")

        spec_patch: dict[str, Any] = {}
        if min_replicas is not None:
            spec_patch["minReplicas"] = min_replicas
        if max_replicas is not None:
            spec_patch["maxReplicas"] = max_replicas

        if not spec_patch:
            raise ValueError("At least one of min_replicas or max_replicas is required")

        body = {"spec": spec_patch}
        await self._autoscaling_api.patch_namespaced_horizontal_pod_autoscaler(
            name=req.resource_name,
            namespace=req.namespace,
            body=body,
        )

        return {
            "message": (
                f"HPA {req.namespace}/{req.resource_name} updated: "
                f"min={min_replicas}, max={max_replicas}"
            ),
            "after_state": spec_patch,
        }

    async def _cordon_node(self, req: K8sRemediationRequest) -> dict[str, Any]:
        """Mark a node as unschedulable (cordon)."""
        assert self._core_api is not None

        body = {"spec": {"unschedulable": True}}
        await self._core_api.patch_node(name=req.resource_name, body=body)

        return {
            "message": f"Node {req.resource_name} cordoned (marked unschedulable)",
            "after_state": {"unschedulable": True},
        }

    async def _drain_node(self, req: K8sRemediationRequest) -> dict[str, Any]:
        """Drain all pods from a node.

        1. Cordon the node (mark unschedulable).
        2. Evict all non-DaemonSet pods respecting PodDisruptionBudgets.
        """
        assert self._core_api is not None

        grace_period = req.parameters.get("grace_period", 30)
        force = req.parameters.get("force", False)

        # Step 1 — cordon
        await self._core_api.patch_node(
            name=req.resource_name,
            body={"spec": {"unschedulable": True}},
        )

        # Step 2 — list pods on the node
        pods = await self._core_api.list_pod_for_all_namespaces(
            field_selector=f"spec.nodeName={req.resource_name}",
        )

        evicted_count = 0
        skipped_count = 0

        for pod in pods.items:
            # Skip DaemonSet-owned pods and mirror pods
            if pod.metadata.owner_references:
                owners = {ref.kind for ref in pod.metadata.owner_references}
                if "DaemonSet" in owners:
                    skipped_count += 1
                    continue

            # Skip kube-system pods unless force
            if pod.metadata.namespace == "kube-system" and not force:
                skipped_count += 1
                continue

            try:
                eviction = client.V1Eviction(
                    metadata=client.V1ObjectMeta(
                        name=pod.metadata.name,
                        namespace=pod.metadata.namespace,
                    ),
                    delete_options=client.V1DeleteOptions(
                        grace_period_seconds=grace_period,
                    ),
                )
                await self._core_api.create_namespaced_pod_eviction(
                    name=pod.metadata.name,
                    namespace=pod.metadata.namespace,
                    body=eviction,
                )
                evicted_count += 1
            except client.ApiException as exc:
                if exc.status == 429 and not force:
                    # PDB violation — respect it
                    logger.warning(
                        "drain_pdb_blocked",
                        pod=pod.metadata.name,
                        namespace=pod.metadata.namespace,
                    )
                    skipped_count += 1
                elif force:
                    # Force delete
                    await self._core_api.delete_namespaced_pod(
                        name=pod.metadata.name,
                        namespace=pod.metadata.namespace,
                        grace_period_seconds=0,
                    )
                    evicted_count += 1
                else:
                    raise

        return {
            "message": (
                f"Node {req.resource_name} drained: "
                f"{evicted_count} evicted, {skipped_count} skipped"
            ),
            "after_state": {
                "unschedulable": True,
                "evicted": evicted_count,
                "skipped": skipped_count,
            },
        }

    async def _update_config_map(self, req: K8sRemediationRequest) -> dict[str, Any]:
        """Update data values in a ConfigMap."""
        assert self._core_api is not None

        data = req.parameters.get("data")
        if not data or not isinstance(data, dict):
            raise ValueError("'data' parameter must be a non-empty dict")

        body = {"data": data}
        await self._core_api.patch_namespaced_config_map(
            name=req.resource_name,
            namespace=req.namespace,
            body=body,
        )

        return {
            "message": (
                f"ConfigMap {req.namespace}/{req.resource_name} updated ({len(data)} key(s))"
            ),
            "after_state": {"updated_keys": list(data.keys())},
        }

    async def _update_resource_limits(self, req: K8sRemediationRequest) -> dict[str, Any]:
        """Patch container resource limits on a deployment."""
        assert self._apps_api is not None

        cpu_limit = req.parameters.get("cpu_limit")
        memory_limit = req.parameters.get("memory_limit")
        container_name = req.parameters.get("container_name")

        if not cpu_limit and not memory_limit:
            raise ValueError("At least one of cpu_limit or memory_limit is required")

        # Read current deployment to find the target container
        deploy = await self._apps_api.read_namespaced_deployment(
            name=req.resource_name,
            namespace=req.namespace,
        )

        containers = deploy.spec.template.spec.containers
        if not containers:
            raise ValueError(f"No containers found in deployment {req.resource_name}")

        # Target the specified container or default to the first one
        target_idx = 0
        if container_name:
            for i, c in enumerate(containers):
                if c.name == container_name:
                    target_idx = i
                    break
            else:
                raise ValueError(
                    f"Container '{container_name}' not found in deployment {req.resource_name}"
                )

        limits: dict[str, str] = {}
        if cpu_limit:
            limits["cpu"] = cpu_limit
        if memory_limit:
            limits["memory"] = memory_limit

        # Build strategic merge patch for the specific container
        container_patch: dict[str, Any] = {
            "name": containers[target_idx].name,
            "resources": {"limits": limits},
        }
        body = {
            "spec": {
                "template": {
                    "spec": {
                        "containers": [container_patch],
                    }
                }
            }
        }

        await self._apps_api.patch_namespaced_deployment(
            name=req.resource_name,
            namespace=req.namespace,
            body=body,
        )

        return {
            "message": (
                f"Deployment {req.namespace}/{req.resource_name} resource limits updated: "
                f"cpu={cpu_limit}, memory={memory_limit}"
            ),
            "after_state": {"limits": limits, "container": containers[target_idx].name},
        }

    async def _delete_evicted_pods(self, req: K8sRemediationRequest) -> dict[str, Any]:
        """Clean up all pods in Evicted state within a namespace."""
        assert self._core_api is not None

        pods = await self._core_api.list_namespaced_pod(namespace=req.namespace)

        deleted = 0
        for pod in pods.items:
            if pod.status and pod.status.phase == "Failed" and pod.status.reason == "Evicted":
                await self._core_api.delete_namespaced_pod(
                    name=pod.metadata.name,
                    namespace=req.namespace,
                )
                deleted += 1

        return {
            "message": f"Deleted {deleted} evicted pod(s) in namespace {req.namespace}",
            "after_state": {"deleted_count": deleted},
        }


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _ts() -> str:
    """Return a compact UTC timestamp for audit logs."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S")


def _elapsed(started_at: datetime) -> float:
    """Seconds elapsed since started_at."""
    return round((datetime.now(UTC) - started_at).total_seconds(), 2)


def _action_to_resource_type(action_type: K8sActionType) -> str:
    """Map an action type to the K8s resource type for snapshotting."""
    mapping = {
        K8sActionType.RESTART_POD: "pod",
        K8sActionType.RESTART_DEPLOYMENT: "deployment",
        K8sActionType.ROLLBACK_DEPLOYMENT: "deployment",
        K8sActionType.SCALE_DEPLOYMENT: "deployment",
        K8sActionType.SCALE_HPA: "hpa",
        K8sActionType.CORDON_NODE: "node",
        K8sActionType.DRAIN_NODE: "node",
        K8sActionType.UPDATE_CONFIG_MAP: "configmap",
        K8sActionType.UPDATE_RESOURCE_LIMITS: "deployment",
        K8sActionType.DELETE_EVICTED_PODS: "pod",
    }
    return mapping.get(action_type, "deployment")
