export type SEOCategory = "kubernetes" | "aws" | "security" | "performance" | "networking";
export type SEOSeverity = "critical" | "high" | "medium";

export interface SEOPage {
  slug: string;
  title: string;
  metaDescription: string;
  category: SEOCategory;
  severity: SEOSeverity;
  symptoms: string[];
  causes: string[];
  manualSteps: string[];
  agentFix: string;
  agentTime: string;
  relatedPages: string[];
}

export const SEO_PAGES: SEOPage[] = [
  // ─── Kubernetes (20) ────────────────────────────────────────────────
  {
    slug: "fix-pod-crashloopbackoff",
    title: "How to Fix Pod CrashLoopBackOff in Kubernetes",
    metaDescription:
      "Learn how to diagnose and fix Kubernetes Pod CrashLoopBackOff errors. Covers common causes like OOM, misconfigurations, and missing dependencies with step-by-step solutions.",
    category: "kubernetes",
    severity: "critical",
    symptoms: [
      "Pod status shows CrashLoopBackOff in kubectl get pods",
      "Pod restart count keeps incrementing",
      "Container exits immediately after starting",
      "Events show Back-off restarting failed container",
    ],
    causes: [
      "Application crashes on startup due to missing environment variables or config",
      "Out of memory (OOM) kill by the kernel — container exceeds memory limits",
      "Liveness probe failing, causing kubelet to restart the container",
      "Missing dependencies such as a database or external service not reachable",
      "Incorrect container command or entrypoint",
    ],
    manualSteps: [
      "Run `kubectl describe pod <pod-name>` to check events and exit codes",
      "Run `kubectl logs <pod-name> --previous` to see logs from the crashed container",
      "Check exit code: 137 = OOM killed, 1 = application error, 126 = command not found",
      "Verify environment variables and ConfigMaps are correctly mounted",
      "Increase memory limits if OOM, fix application code if exit code 1",
      "Check liveness probe configuration and increase initialDelaySeconds if needed",
    ],
    agentFix:
      "ShieldOps Investigation Agent automatically detects CrashLoopBackOff events, pulls container logs, correlates exit codes with known patterns, identifies root cause (OOM, missing config, probe failure), and either adjusts resource limits, patches configuration, or escalates with a full root cause analysis.",
    agentTime: "47 seconds",
    relatedPages: [
      "fix-pod-oomkilled",
      "fix-liveness-probe-failure",
      "fix-configmap-mount-error",
    ],
  },
  {
    slug: "fix-pod-oomkilled",
    title: "How to Fix OOMKilled Pods in Kubernetes",
    metaDescription:
      "Resolve Kubernetes OOMKilled errors. Understand why pods get killed for exceeding memory limits and how to right-size resources.",
    category: "kubernetes",
    severity: "critical",
    symptoms: [
      "Pod status shows OOMKilled",
      "Exit code 137 in container status",
      "Application becomes unresponsive before restart",
      "Kernel OOM messages in node dmesg logs",
    ],
    causes: [
      "Memory limits set too low for the workload",
      "Memory leak in the application",
      "JVM heap not aligned with container memory limits",
      "Sidecar containers consuming unexpected memory",
      "Large in-memory caches or data processing spikes",
    ],
    manualSteps: [
      "Run `kubectl describe pod <pod-name>` and check Last State for OOMKilled",
      "Review current memory limits with `kubectl get pod <pod-name> -o yaml`",
      "Analyze memory usage trends with `kubectl top pod` or Prometheus metrics",
      "Increase memory limits in the deployment spec",
      "Profile the application for memory leaks using language-specific tools",
      "For JVM apps, set -Xmx to ~75% of container memory limit",
    ],
    agentFix:
      "ShieldOps correlates OOMKilled events with historical memory usage from Prometheus, identifies whether the issue is a leak or under-provisioning, and either right-sizes the limits automatically or flags the memory leak with profiling data for developer review.",
    agentTime: "38 seconds",
    relatedPages: [
      "fix-pod-crashloopbackoff",
      "fix-resource-quota-exceeded",
      "fix-cpu-throttling",
    ],
  },
  {
    slug: "fix-imagepullbackoff",
    title: "How to Fix ImagePullBackOff in Kubernetes",
    metaDescription:
      "Fix Kubernetes ImagePullBackOff errors caused by wrong image names, missing credentials, or registry issues. Step-by-step guide.",
    category: "kubernetes",
    severity: "high",
    symptoms: [
      "Pod status shows ImagePullBackOff or ErrImagePull",
      "Events show failed to pull image with authentication or not found errors",
      "New deployments stuck with 0 ready replicas",
      "Rollout hangs indefinitely",
    ],
    causes: [
      "Image tag does not exist in the registry",
      "Registry credentials (imagePullSecrets) missing or expired",
      "Private registry not accessible from cluster network",
      "Image name typo or wrong registry URL",
      "Docker Hub rate limiting (429 Too Many Requests)",
    ],
    manualSteps: [
      "Run `kubectl describe pod <pod-name>` and read the pull error message",
      "Verify the image exists: `docker pull <image>` from your local machine",
      "Check imagePullSecrets: `kubectl get pod <pod-name> -o jsonpath='{.spec.imagePullSecrets}'`",
      "Recreate registry secret: `kubectl create secret docker-registry ...`",
      "Test registry connectivity from a debug pod inside the cluster",
      "If Docker Hub rate limit, configure a pull-through cache or authenticate",
    ],
    agentFix:
      "ShieldOps detects ImagePullBackOff events, verifies image existence in the target registry, checks credential validity and network reachability, then either refreshes expired pull secrets or corrects the image reference automatically.",
    agentTime: "32 seconds",
    relatedPages: [
      "fix-failed-deployment",
      "fix-secret-rotation",
      "fix-pod-crashloopbackoff",
    ],
  },
  {
    slug: "fix-pending-pods",
    title: "How to Fix Pending Pods in Kubernetes",
    metaDescription:
      "Diagnose and resolve Kubernetes pods stuck in Pending state. Covers insufficient resources, node affinity issues, and scheduling failures.",
    category: "kubernetes",
    severity: "high",
    symptoms: [
      "Pod status stuck at Pending for minutes or hours",
      "kubectl describe shows 0/N nodes are available",
      "Deployment shows 0 available replicas",
      "Events mention Insufficient cpu or Insufficient memory",
    ],
    causes: [
      "Cluster has insufficient CPU or memory to schedule the pod",
      "Node affinity or nodeSelector rules prevent scheduling",
      "Taints on nodes with no matching tolerations",
      "PersistentVolumeClaim not bound",
      "ResourceQuota exceeded in the namespace",
    ],
    manualSteps: [
      "Run `kubectl describe pod <pod-name>` and check the Events section",
      "Check node resources: `kubectl describe nodes | grep -A 5 Allocated`",
      "Review pod affinity/nodeSelector: `kubectl get pod <pod-name> -o yaml`",
      "Check taints: `kubectl describe nodes | grep Taints`",
      "Scale up the cluster or adjust resource requests",
      "If PVC issue, check `kubectl get pvc` for Pending volumes",
    ],
    agentFix:
      "ShieldOps analyzes scheduler events, compares pod resource requests against available node capacity, identifies the blocking constraint (resources, affinity, taints, PVC), and either triggers node autoscaling, adjusts resource requests, or resolves PVC binding.",
    agentTime: "55 seconds",
    relatedPages: [
      "fix-resource-quota-exceeded",
      "fix-pvc-pending",
      "fix-node-notready",
    ],
  },
  {
    slug: "fix-evicted-pods",
    title: "How to Fix Evicted Pods in Kubernetes",
    metaDescription:
      "Resolve Kubernetes pod evictions caused by disk pressure, memory pressure, or resource limits. Prevent data loss and downtime.",
    category: "kubernetes",
    severity: "high",
    symptoms: [
      "Pods showing Evicted status in kubectl get pods",
      "Large number of terminated pods accumulating",
      "Node conditions show DiskPressure or MemoryPressure",
      "Application availability drops suddenly",
    ],
    causes: [
      "Node disk pressure — ephemeral storage or container logs filling disk",
      "Node memory pressure — total pod memory exceeding node capacity",
      "Pod exceeding ephemeral storage limits",
      "Priority-based preemption by higher-priority pods",
      "kubelet garbage collection thresholds breached",
    ],
    manualSteps: [
      "Check node conditions: `kubectl describe node <node-name>`",
      "Review eviction events: `kubectl get events --field-selector reason=Evicted`",
      "Check disk usage on the node: `df -h` and `du -sh /var/lib/kubelet`",
      "Clean up old container images and logs",
      "Set ephemeral storage limits on pods",
      "Add PodDisruptionBudgets to protect critical workloads",
    ],
    agentFix:
      "ShieldOps monitors node pressure conditions, identifies pods consuming excessive ephemeral storage, triggers log rotation or image garbage collection, and adjusts eviction thresholds to prevent cascading evictions.",
    agentTime: "41 seconds",
    relatedPages: [
      "fix-node-notready",
      "fix-pod-oomkilled",
      "fix-disk-io-saturation",
    ],
  },
  {
    slug: "fix-node-notready",
    title: "How to Fix Node NotReady in Kubernetes",
    metaDescription:
      "Troubleshoot Kubernetes nodes in NotReady state. Diagnose kubelet failures, network issues, and resource exhaustion on cluster nodes.",
    category: "kubernetes",
    severity: "critical",
    symptoms: [
      "kubectl get nodes shows one or more nodes as NotReady",
      "Pods on affected nodes being evicted or rescheduled",
      "Node heartbeat not received by API server",
      "Cluster autoscaler cannot provision replacements",
    ],
    causes: [
      "kubelet process crashed or not running",
      "Node ran out of disk space, memory, or PIDs",
      "Network partition between node and control plane",
      "Container runtime (containerd/Docker) unresponsive",
      "Kernel panic or hardware failure on the node",
    ],
    manualSteps: [
      "SSH into the node and check kubelet: `systemctl status kubelet`",
      "Review kubelet logs: `journalctl -u kubelet --since '10 minutes ago'`",
      "Check container runtime: `systemctl status containerd`",
      "Verify disk space: `df -h` and memory: `free -m`",
      "Restart kubelet: `systemctl restart kubelet`",
      "If unrecoverable, cordon and drain the node, then replace it",
    ],
    agentFix:
      "ShieldOps detects NotReady node events, SSHes into the node to diagnose kubelet and container runtime health, restarts failed services, and if the node is unrecoverable, automatically cordons, drains, and triggers replacement via the cloud provider autoscaler.",
    agentTime: "63 seconds",
    relatedPages: [
      "fix-evicted-pods",
      "fix-pending-pods",
      "fix-coredns-timeout",
    ],
  },
  {
    slug: "fix-dns-failures-kubernetes",
    title: "How to Fix DNS Failures in Kubernetes",
    metaDescription:
      "Resolve Kubernetes DNS resolution failures. Troubleshoot CoreDNS issues, service discovery problems, and DNS misconfigurations.",
    category: "kubernetes",
    severity: "critical",
    symptoms: [
      "Application logs show DNS resolution errors or host not found",
      "Pods cannot resolve service names or external domains",
      "nslookup from debug pods fails intermittently",
      "Increased latency on service-to-service calls",
    ],
    causes: [
      "CoreDNS pods crashed or overloaded",
      "Cluster DNS service (kube-dns) IP unreachable",
      "Network policy blocking DNS traffic on port 53",
      "Node-level DNS configuration overriding cluster DNS",
      "ndots setting causing excessive DNS queries",
    ],
    manualSteps: [
      "Check CoreDNS pods: `kubectl get pods -n kube-system -l k8s-app=kube-dns`",
      "Test DNS from a debug pod: `kubectl exec -it <pod> -- nslookup kubernetes.default`",
      "Check CoreDNS logs: `kubectl logs -n kube-system -l k8s-app=kube-dns`",
      "Verify network policies allow UDP/TCP port 53",
      "Review resolv.conf in pods: `kubectl exec <pod> -- cat /etc/resolv.conf`",
      "Scale CoreDNS if overloaded: `kubectl scale deployment coredns -n kube-system --replicas=3`",
    ],
    agentFix:
      "ShieldOps detects DNS failure patterns across pods, checks CoreDNS health and query latency, identifies whether the issue is capacity, network policy, or misconfiguration, then scales CoreDNS, adjusts network policies, or fixes ndots settings.",
    agentTime: "44 seconds",
    relatedPages: [
      "fix-coredns-timeout",
      "fix-service-unreachable",
      "fix-network-policy-blocking",
    ],
  },
  {
    slug: "fix-failed-deployment",
    title: "How to Fix Failed Deployment Rollouts in Kubernetes",
    metaDescription:
      "Troubleshoot Kubernetes deployment failures. Fix stuck rollouts, failed replicas, and deployment deadline exceeded errors.",
    category: "kubernetes",
    severity: "high",
    symptoms: [
      "kubectl rollout status shows deployment has not progressed",
      "New ReplicaSet has 0 ready pods",
      "Old ReplicaSet still running with full replica count",
      "Events show ProgressDeadlineExceeded",
    ],
    causes: [
      "New pods crashing (CrashLoopBackOff) preventing rollout completion",
      "ImagePullBackOff on the new image version",
      "Readiness probe failing on new pods",
      "Insufficient cluster resources to schedule new pods",
      "Misconfigured deployment strategy (maxUnavailable=0 with no room to surge)",
    ],
    manualSteps: [
      "Check rollout status: `kubectl rollout status deployment/<name>`",
      "Describe the deployment: `kubectl describe deployment <name>`",
      "Check new ReplicaSet pods: `kubectl get pods -l app=<name> --sort-by=.metadata.creationTimestamp`",
      "Review pod logs and events for the failing pods",
      "Rollback if needed: `kubectl rollout undo deployment/<name>`",
      "Fix the underlying issue and redeploy",
    ],
    agentFix:
      "ShieldOps detects stalled rollouts, inspects new ReplicaSet pod health, identifies the blocking issue (crash, image, probe, resources), automatically rolls back if the error rate exceeds thresholds, and provides a detailed root cause report.",
    agentTime: "52 seconds",
    relatedPages: [
      "fix-pod-crashloopbackoff",
      "fix-imagepullbackoff",
      "fix-liveness-probe-failure",
    ],
  },
  {
    slug: "fix-hpa-not-scaling",
    title: "How to Fix HPA Not Scaling in Kubernetes",
    metaDescription:
      "Resolve Kubernetes Horizontal Pod Autoscaler not scaling issues. Fix metrics unavailability, target thresholds, and scaling limits.",
    category: "kubernetes",
    severity: "medium",
    symptoms: [
      "HPA shows <unknown> for current metrics",
      "Pod count stays at minReplicas despite high load",
      "HPA events show failed to get metrics or missing request for cpu",
      "Application latency increasing but no scale-up happening",
    ],
    causes: [
      "Metrics server not installed or not running",
      "Pod resource requests not set (required for CPU-based HPA)",
      "Custom metrics adapter misconfigured",
      "HPA minReplicas equals maxReplicas",
      "Scale-down stabilization window preventing changes",
    ],
    manualSteps: [
      "Check HPA status: `kubectl get hpa` and `kubectl describe hpa <name>`",
      "Verify metrics server: `kubectl get pods -n kube-system | grep metrics-server`",
      "Ensure pods have CPU/memory requests defined in the deployment spec",
      "Test metrics availability: `kubectl top pods`",
      "Check HPA events for specific error messages",
      "If using custom metrics, verify the metrics adapter is running",
    ],
    agentFix:
      "ShieldOps validates the entire HPA pipeline — metrics server health, resource requests, adapter configuration, and scaling parameters — then fixes the identified gap, whether it is deploying metrics server, adding resource requests, or adjusting HPA targets.",
    agentTime: "35 seconds",
    relatedPages: [
      "fix-pod-oomkilled",
      "fix-cpu-throttling",
      "fix-resource-quota-exceeded",
    ],
  },
  {
    slug: "fix-pvc-pending",
    title: "How to Fix PVC Pending in Kubernetes",
    metaDescription:
      "Resolve Kubernetes PersistentVolumeClaim stuck in Pending state. Fix storage class issues, provisioner errors, and volume binding problems.",
    category: "kubernetes",
    severity: "high",
    symptoms: [
      "PVC status shows Pending indefinitely",
      "Pods referencing the PVC stuck in Pending",
      "Events show no persistent volumes available or provisioning failed",
      "StatefulSet not creating new pods",
    ],
    causes: [
      "No StorageClass matches the PVC request",
      "Cloud storage provisioner quota exceeded",
      "StorageClass provisioner not installed or crashing",
      "VolumeBindingMode is WaitForFirstConsumer but no pod is scheduled",
      "Requested storage size exceeds available capacity",
    ],
    manualSteps: [
      "Check PVC status: `kubectl get pvc` and `kubectl describe pvc <name>`",
      "List StorageClasses: `kubectl get storageclass`",
      "Verify the PVC storageClassName matches an available StorageClass",
      "Check provisioner pods: `kubectl get pods -n kube-system`",
      "Check cloud provider quotas for EBS/PD/Azure Disk volumes",
      "If WaitForFirstConsumer, ensure a pod is requesting the PVC",
    ],
    agentFix:
      "ShieldOps identifies the PVC binding failure, checks storage class availability, provisioner health, and cloud quotas, then resolves by fixing storage class references, restarting provisioners, or requesting quota increases.",
    agentTime: "40 seconds",
    relatedPages: [
      "fix-pending-pods",
      "fix-failed-deployment",
      "fix-resource-quota-exceeded",
    ],
  },
  {
    slug: "fix-ingress-502",
    title: "How to Fix Ingress 502 Bad Gateway in Kubernetes",
    metaDescription:
      "Troubleshoot Kubernetes Ingress 502 Bad Gateway errors. Fix backend service issues, health check failures, and ingress controller misconfigurations.",
    category: "kubernetes",
    severity: "critical",
    symptoms: [
      "Users receiving 502 Bad Gateway errors from the Ingress endpoint",
      "Ingress controller logs show upstream connection refused or reset",
      "Health checks failing for backend services",
      "Intermittent 502s during deployments",
    ],
    causes: [
      "Backend pods not ready or crashing",
      "Service selector does not match pod labels",
      "Readiness probe misconfigured — pods removed from endpoints too late",
      "Ingress controller cannot reach backend service (network policy or port mismatch)",
      "SSL/TLS termination misconfiguration",
    ],
    manualSteps: [
      "Check backend pod health: `kubectl get pods -l <selector>`",
      "Verify endpoints exist: `kubectl get endpoints <service-name>`",
      "Review ingress controller logs for upstream errors",
      "Test service directly: `kubectl port-forward svc/<name> 8080:<port>`",
      "Check if readiness probes are passing on backend pods",
      "Verify Ingress annotations match the ingress controller type",
    ],
    agentFix:
      "ShieldOps traces the 502 from ingress controller to backend, checks endpoint health, pod readiness, service selectors, and port mappings, then remediates by restarting unhealthy backends or correcting misconfigurations.",
    agentTime: "51 seconds",
    relatedPages: [
      "fix-service-unreachable",
      "fix-liveness-probe-failure",
      "fix-failed-deployment",
    ],
  },
  {
    slug: "fix-service-unreachable",
    title: "How to Fix Service Unreachable in Kubernetes",
    metaDescription:
      "Diagnose and fix Kubernetes service connectivity issues. Resolve selector mismatches, endpoint problems, and kube-proxy failures.",
    category: "kubernetes",
    severity: "high",
    symptoms: [
      "Connection refused or timeout when accessing a Kubernetes Service",
      "curl to ClusterIP returns no route to host",
      "Service endpoints list is empty",
      "Inter-service calls failing across namespaces",
    ],
    causes: [
      "Service selector does not match any pod labels",
      "Target port in Service spec does not match container port",
      "kube-proxy not running or iptables rules corrupted",
      "Network policy blocking traffic between namespaces",
      "Pod is running but readiness probe failing, removing it from endpoints",
    ],
    manualSteps: [
      "Check endpoints: `kubectl get endpoints <service-name>`",
      "Verify selectors match: compare `kubectl get svc <name> -o yaml` with pod labels",
      "Test pod directly: `kubectl exec -it <pod> -- curl localhost:<port>`",
      "Check kube-proxy: `kubectl get pods -n kube-system -l k8s-app=kube-proxy`",
      "Review network policies: `kubectl get networkpolicies`",
      "Restart kube-proxy if iptables are corrupted",
    ],
    agentFix:
      "ShieldOps maps the full service-to-pod path, validates label selectors, port mappings, kube-proxy health, and network policies, then fixes the root cause automatically — whether it is a selector mismatch, port misconfiguration, or network policy gap.",
    agentTime: "43 seconds",
    relatedPages: [
      "fix-ingress-502",
      "fix-network-policy-blocking",
      "fix-dns-failures-kubernetes",
    ],
  },
  {
    slug: "fix-configmap-mount-error",
    title: "How to Fix ConfigMap Mount Errors in Kubernetes",
    metaDescription:
      "Resolve Kubernetes ConfigMap mount failures. Fix missing ConfigMaps, key errors, and volume mount misconfigurations.",
    category: "kubernetes",
    severity: "medium",
    symptoms: [
      "Pod stuck in ContainerCreating with mount error events",
      "Events show configmap not found or key not found in configmap",
      "Application starts but configuration values are empty",
      "Pod fails with file not found errors for config paths",
    ],
    causes: [
      "ConfigMap does not exist in the same namespace as the pod",
      "ConfigMap key referenced in the volume does not exist",
      "Typo in ConfigMap name or key reference",
      "ConfigMap created after the pod was scheduled",
      "subPath mount preventing live ConfigMap updates",
    ],
    manualSteps: [
      "Check if ConfigMap exists: `kubectl get configmap <name>`",
      "Describe the pod to see mount error details: `kubectl describe pod <name>`",
      "Verify ConfigMap keys: `kubectl get configmap <name> -o yaml`",
      "Ensure ConfigMap is in the same namespace as the pod",
      "Recreate or update the ConfigMap and restart the pod",
      "If using subPath, note that updates require pod restart",
    ],
    agentFix:
      "ShieldOps detects ConfigMap mount failures, cross-references the pod spec with available ConfigMaps in the namespace, identifies the missing or mismatched reference, and either creates the missing ConfigMap from known templates or corrects the reference.",
    agentTime: "28 seconds",
    relatedPages: [
      "fix-pod-crashloopbackoff",
      "fix-secret-rotation",
      "fix-failed-deployment",
    ],
  },
  {
    slug: "fix-secret-rotation",
    title: "How to Fix Kubernetes Secret Rotation Issues",
    metaDescription:
      "Handle Kubernetes Secret rotation safely. Manage expired credentials, certificate renewals, and secret update propagation.",
    category: "kubernetes",
    severity: "high",
    symptoms: [
      "Application authentication failures after credential rotation",
      "Pods still using old secret values after an update",
      "Database connection errors with authentication failed",
      "TLS handshake failures after certificate renewal",
    ],
    causes: [
      "Secret updated but pods not restarted to pick up new values",
      "subPath volume mount prevents automatic secret propagation",
      "Application caches credentials at startup and does not reload",
      "Multiple services reference the same secret with different update schedules",
      "Secret not updated in all required namespaces",
    ],
    manualSteps: [
      "Update the secret: `kubectl create secret generic <name> --from-literal=... --dry-run=client -o yaml | kubectl apply -f -`",
      "Restart pods to pick up changes: `kubectl rollout restart deployment/<name>`",
      "Verify new secret is mounted: `kubectl exec <pod> -- cat /path/to/secret`",
      "If using external-secrets-operator, check sync status",
      "Coordinate rotation across all dependent services",
      "Test connectivity after rotation",
    ],
    agentFix:
      "ShieldOps orchestrates secret rotation across all dependent deployments, updates secrets, triggers rolling restarts, verifies connectivity post-rotation, and rolls back if any service health check fails.",
    agentTime: "72 seconds",
    relatedPages: [
      "fix-certificate-expiry-k8s",
      "fix-configmap-mount-error",
      "fix-api-key-leaked",
    ],
  },
  {
    slug: "fix-certificate-expiry-k8s",
    title: "How to Fix Certificate Expiry in Kubernetes",
    metaDescription:
      "Prevent and fix TLS certificate expiry in Kubernetes. Manage cert-manager renewals, Ingress TLS, and internal PKI.",
    category: "kubernetes",
    severity: "critical",
    symptoms: [
      "TLS handshake failures and certificate expired errors",
      "Browsers showing NET::ERR_CERT_DATE_INVALID",
      "Ingress returning 503 with TLS termination errors",
      "Internal service-to-service mTLS failures",
    ],
    causes: [
      "cert-manager not renewing certificates before expiry",
      "Certificate Issuer (Let's Encrypt) rate limited or misconfigured",
      "Manual certificates expired without monitoring",
      "Kubernetes API server certificates expired (cluster-breaking)",
      "CA bundle not updated across services",
    ],
    manualSteps: [
      "Check certificate expiry: `kubectl get certificate -A`",
      "Describe the certificate: `kubectl describe certificate <name>`",
      "Check cert-manager logs: `kubectl logs -n cert-manager deploy/cert-manager`",
      "Manually renew: `cmctl renew <certificate-name>`",
      "For API server certs, use kubeadm: `kubeadm certs renew all`",
      "Update CA bundles in ConfigMaps and restart affected pods",
    ],
    agentFix:
      "ShieldOps continuously monitors certificate expiry dates, triggers cert-manager renewals proactively, verifies new certificates are propagated, and alerts on any certificates within 30 days of expiry with automated renewal workflows.",
    agentTime: "58 seconds",
    relatedPages: [
      "fix-tls-certificate-expiry",
      "fix-secret-rotation",
      "fix-ingress-502",
    ],
  },
  {
    slug: "fix-resource-quota-exceeded",
    title: "How to Fix Resource Quota Exceeded in Kubernetes",
    metaDescription:
      "Resolve Kubernetes ResourceQuota exceeded errors. Manage namespace quotas, optimize resource requests, and handle quota conflicts.",
    category: "kubernetes",
    severity: "medium",
    symptoms: [
      "Pod creation fails with forbidden: exceeded quota",
      "Deployments cannot scale up despite cluster capacity",
      "HPA scaling blocked by namespace quota limits",
      "kubectl describe quota shows usage at or near limits",
    ],
    causes: [
      "Namespace ResourceQuota limits are too restrictive",
      "Pod resource requests are over-provisioned",
      "Orphaned resources consuming quota (completed Jobs, old ReplicaSets)",
      "LimitRange defaults setting higher requests than needed",
      "Multiple teams sharing a namespace without clear budgets",
    ],
    manualSteps: [
      "Check quota usage: `kubectl describe resourcequota -n <namespace>`",
      "List all resource consumers: `kubectl get pods -n <namespace> -o wide`",
      "Clean up completed Jobs: `kubectl delete jobs --field-selector status.successful=1`",
      "Right-size pod resource requests based on actual usage",
      "Request quota increase from cluster admin if legitimately needed",
      "Consider splitting workloads across namespaces",
    ],
    agentFix:
      "ShieldOps analyzes quota usage vs. actual resource consumption, identifies over-provisioned pods and orphaned resources, right-sizes requests based on historical metrics, and cleans up unused resources to free quota.",
    agentTime: "46 seconds",
    relatedPages: [
      "fix-pending-pods",
      "fix-hpa-not-scaling",
      "fix-pod-oomkilled",
    ],
  },
  {
    slug: "fix-network-policy-blocking",
    title: "How to Fix Network Policy Blocking Traffic in Kubernetes",
    metaDescription:
      "Troubleshoot Kubernetes NetworkPolicy blocking legitimate traffic. Debug ingress/egress rules and allow proper service communication.",
    category: "kubernetes",
    severity: "high",
    symptoms: [
      "Service-to-service calls timing out after NetworkPolicy deployment",
      "Pods can no longer reach external endpoints",
      "DNS resolution fails in pods with strict network policies",
      "Ingress traffic blocked despite correct Ingress resource",
    ],
    causes: [
      "Default-deny policy applied without explicit allow rules",
      "NetworkPolicy selectors do not match intended pods",
      "Missing egress rule for DNS (UDP port 53)",
      "CIDR ranges in policies excluding necessary subnets",
      "CNI plugin does not support NetworkPolicy (e.g., default kubenet)",
    ],
    manualSteps: [
      "List network policies: `kubectl get networkpolicies -n <namespace>`",
      "Describe the policy: `kubectl describe networkpolicy <name>`",
      "Test connectivity: `kubectl exec <pod> -- curl -v <target>`",
      "Ensure DNS egress is allowed: allow UDP/TCP 53 to kube-dns",
      "Verify CNI plugin supports NetworkPolicy (Calico, Cilium, etc.)",
      "Temporarily remove the policy to confirm it is the cause",
    ],
    agentFix:
      "ShieldOps maps pod communication patterns, compares against active NetworkPolicies, identifies which rules are blocking legitimate traffic, and generates corrected policies that maintain security while restoring connectivity.",
    agentTime: "56 seconds",
    relatedPages: [
      "fix-service-unreachable",
      "fix-dns-failures-kubernetes",
      "fix-ingress-502",
    ],
  },
  {
    slug: "fix-coredns-timeout",
    title: "How to Fix CoreDNS Timeouts in Kubernetes",
    metaDescription:
      "Resolve CoreDNS timeout issues in Kubernetes. Fix slow DNS resolution, high query latency, and CoreDNS performance problems.",
    category: "kubernetes",
    severity: "high",
    symptoms: [
      "DNS queries taking 5+ seconds before resolving",
      "Intermittent DNS timeout errors in application logs",
      "CoreDNS pods showing high CPU or memory usage",
      "Increased latency across all services simultaneously",
    ],
    causes: [
      "CoreDNS pods under-replicated for cluster size",
      "CONNTRACK table full on nodes causing packet drops",
      "DNS race condition on Linux (known kernel bug with UDP)",
      "Upstream DNS server slow or unreachable",
      "Excessive DNS queries due to ndots:5 default",
    ],
    manualSteps: [
      "Check CoreDNS pod count and resource usage: `kubectl top pods -n kube-system -l k8s-app=kube-dns`",
      "Scale CoreDNS: `kubectl scale deployment coredns -n kube-system --replicas=5`",
      "Check conntrack: `conntrack -C` on affected nodes",
      "Add `options single-request-reopen` to resolv.conf via dnsConfig",
      "Reduce ndots in pod spec to avoid unnecessary search domain lookups",
      "Check upstream DNS: `kubectl exec <coredns-pod> -n kube-system -- dig @<upstream> google.com`",
    ],
    agentFix:
      "ShieldOps profiles CoreDNS query patterns, identifies bottlenecks (capacity, conntrack, upstream), scales CoreDNS replicas, applies DNS configuration optimizations, and monitors resolution times to verify the fix.",
    agentTime: "49 seconds",
    relatedPages: [
      "fix-dns-failures-kubernetes",
      "fix-dns-resolution-failure",
      "fix-node-notready",
    ],
  },
  {
    slug: "fix-liveness-probe-failure",
    title: "How to Fix Liveness Probe Failures in Kubernetes",
    metaDescription:
      "Troubleshoot Kubernetes liveness probe failures causing unnecessary pod restarts. Configure probes correctly for your application.",
    category: "kubernetes",
    severity: "high",
    symptoms: [
      "Pod repeatedly restarting with liveness probe failed in events",
      "Application is functional but kubelet keeps killing it",
      "High restart count on otherwise healthy pods",
      "Container killed message with exit code 137",
    ],
    causes: [
      "initialDelaySeconds too short for application startup time",
      "Probe endpoint doing heavy work (database queries, external calls)",
      "timeoutSeconds too low for slow health check responses",
      "Application deadlocked but HTTP server still accepting connections",
      "Resource contention causing probe to timeout under load",
    ],
    manualSteps: [
      "Check probe config: `kubectl get pod <name> -o jsonpath='{.spec.containers[*].livenessProbe}'`",
      "Test probe endpoint manually: `kubectl exec <pod> -- curl -v localhost:<port><path>`",
      "Review restart events: `kubectl describe pod <name>`",
      "Increase initialDelaySeconds for slow-starting apps",
      "Increase timeoutSeconds and failureThreshold",
      "Ensure the probe endpoint is lightweight and does not call external services",
    ],
    agentFix:
      "ShieldOps correlates probe failures with application startup time and resource usage, automatically adjusts probe timing parameters (initialDelaySeconds, timeout, threshold) based on observed application behavior, and verifies stability post-change.",
    agentTime: "33 seconds",
    relatedPages: [
      "fix-pod-crashloopbackoff",
      "fix-ingress-502",
      "fix-init-container-failure",
    ],
  },
  {
    slug: "fix-init-container-failure",
    title: "How to Fix Init Container Failures in Kubernetes",
    metaDescription:
      "Resolve Kubernetes Init container failures blocking pod startup. Debug dependency checks, migration scripts, and initialization errors.",
    category: "kubernetes",
    severity: "medium",
    symptoms: [
      "Pod stuck in Init:0/1 or Init:Error status",
      "Main containers never start",
      "Init container logs show connection refused or timeout",
      "Deployment rollout stalled with pods in Init state",
    ],
    causes: [
      "Init container waiting for a dependency (database, service) that is not ready",
      "Database migration script failing in init container",
      "Init container image not available (ImagePullBackOff)",
      "Init container command has a bug or typo",
      "Network policy preventing init container from reaching external services",
    ],
    manualSteps: [
      "Check init container status: `kubectl describe pod <name>`",
      "View init container logs: `kubectl logs <pod> -c <init-container-name>`",
      "Verify the dependency the init container is waiting for is healthy",
      "Test the init command manually in a debug pod",
      "If a migration, check database connectivity and migration state",
      "Fix the init container command/image and redeploy",
    ],
    agentFix:
      "ShieldOps identifies the failing init container, inspects logs and exit codes, verifies dependency health, and either fixes the dependency issue or adjusts the init container configuration to resolve the startup blocker.",
    agentTime: "37 seconds",
    relatedPages: [
      "fix-pod-crashloopbackoff",
      "fix-failed-deployment",
      "fix-configmap-mount-error",
    ],
  },
  // ─── AWS (10) ───────────────────────────────────────────────────────
  {
    slug: "fix-ec2-instance-unreachable",
    title: "How to Fix EC2 Instance Unreachable",
    metaDescription:
      "Troubleshoot unreachable AWS EC2 instances. Diagnose security groups, network ACLs, instance status checks, and SSH connectivity issues.",
    category: "aws",
    severity: "critical",
    symptoms: [
      "Cannot SSH or connect to EC2 instance",
      "Instance status checks showing impaired",
      "Application hosted on EC2 not responding",
      "CloudWatch alarms firing for StatusCheckFailed",
    ],
    causes: [
      "Security group inbound rules blocking access",
      "Network ACL denying traffic",
      "Instance in a private subnet without NAT gateway",
      "Instance kernel panic or OS-level crash",
      "EBS volume full or detached",
    ],
    manualSteps: [
      "Check instance status in AWS Console: EC2 > Instances > Status Checks",
      "Verify security group rules allow your IP on required ports",
      "Check VPC Network ACLs for deny rules",
      "Check route tables for the instance subnet",
      "Use EC2 Serial Console or SSM Session Manager for out-of-band access",
      "If status check failed, stop and start the instance (new host)",
    ],
    agentFix:
      "ShieldOps detects StatusCheckFailed alarms, diagnoses security groups, NACLs, and route tables, attempts out-of-band recovery via SSM, and if the instance is unrecoverable, launches a replacement from the latest AMI with the same configuration.",
    agentTime: "68 seconds",
    relatedPages: [
      "fix-iam-permission-denied",
      "fix-alb-5xx-spike",
      "fix-s3-access-denied",
    ],
  },
  {
    slug: "fix-rds-connection-limit",
    title: "How to Fix RDS Connection Limit Exceeded",
    metaDescription:
      "Resolve AWS RDS max connection limit errors. Optimize connection pooling, right-size instances, and fix connection leaks.",
    category: "aws",
    severity: "critical",
    symptoms: [
      "Application errors: too many connections",
      "New database connections rejected",
      "RDS CloudWatch showing DatabaseConnections at max",
      "Intermittent query timeouts",
    ],
    causes: [
      "Connection pool size misconfigured across multiple services",
      "Connection leaks — connections not properly returned to pool",
      "RDS instance class too small (max_connections derived from instance memory)",
      "Lambda functions opening new connections per invocation without pooling",
      "Idle connections not being reaped by application or proxy",
    ],
    manualSteps: [
      "Check current connections: `SELECT count(*) FROM pg_stat_activity;`",
      "Identify top consumers: `SELECT usename, count(*) FROM pg_stat_activity GROUP BY usename;`",
      "Kill idle connections: `SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE state = 'idle' AND query_start < now() - interval '10 minutes';`",
      "Review connection pool settings in application configuration",
      "Consider using RDS Proxy for connection pooling",
      "Upgrade RDS instance class for higher max_connections",
    ],
    agentFix:
      "ShieldOps monitors connection counts across all RDS instances, identifies connection leaks by correlating per-service pool usage, terminates idle connections, and recommends or deploys RDS Proxy for services with connection management issues.",
    agentTime: "54 seconds",
    relatedPages: [
      "fix-connection-pool-exhaustion",
      "fix-lambda-timeout",
      "fix-high-p99-latency",
    ],
  },
  {
    slug: "fix-s3-access-denied",
    title: "How to Fix S3 Access Denied Errors",
    metaDescription:
      "Resolve AWS S3 Access Denied (403) errors. Debug bucket policies, IAM policies, VPC endpoints, and cross-account access.",
    category: "aws",
    severity: "high",
    symptoms: [
      "S3 API calls return 403 Access Denied",
      "Application cannot read or write to S3 bucket",
      "Cross-account S3 access failing",
      "S3 presigned URLs returning AccessDenied",
    ],
    causes: [
      "IAM policy missing required s3:GetObject or s3:PutObject permissions",
      "Bucket policy explicitly denying access",
      "S3 Block Public Access settings overriding bucket policy",
      "VPC endpoint policy restricting bucket access",
      "Object ACLs set to private in a cross-account scenario",
    ],
    manualSteps: [
      "Check IAM policy: use IAM Policy Simulator in AWS Console",
      "Review bucket policy: `aws s3api get-bucket-policy --bucket <name>`",
      "Check Block Public Access: `aws s3api get-public-access-block --bucket <name>`",
      "Verify VPC endpoint policy if accessing from private subnet",
      "For cross-account, ensure bucket policy grants access to the external account",
      "Check object ownership: `aws s3api get-object-acl --bucket <name> --key <key>`",
    ],
    agentFix:
      "ShieldOps traces the S3 access path, evaluates IAM policies, bucket policies, ACLs, and VPC endpoint policies, identifies the specific deny, and generates the minimal policy fix while maintaining least-privilege security.",
    agentTime: "42 seconds",
    relatedPages: [
      "fix-iam-permission-denied",
      "fix-unauthorized-api-access",
      "fix-ec2-instance-unreachable",
    ],
  },
  {
    slug: "fix-lambda-timeout",
    title: "How to Fix AWS Lambda Timeout Errors",
    metaDescription:
      "Resolve AWS Lambda function timeout issues. Optimize cold starts, fix downstream dependencies, and configure timeout settings.",
    category: "aws",
    severity: "high",
    symptoms: [
      "Lambda function errors with Task timed out after X seconds",
      "Intermittent Lambda failures under load",
      "Lambda duration approaching the configured timeout",
      "API Gateway returning 504 Gateway Timeout",
    ],
    causes: [
      "Downstream service (database, API) slow or unreachable",
      "Lambda timeout configured too low for the workload",
      "Cold start adding significant latency (VPC Lambda)",
      "Large payload processing exceeding time budget",
      "DNS resolution delays in VPC-attached Lambdas",
    ],
    manualSteps: [
      "Check Lambda logs in CloudWatch for timeout events",
      "Review function duration metrics and identify spikes",
      "Test downstream dependencies independently",
      "Increase timeout setting (max 900 seconds) if appropriate",
      "Use provisioned concurrency to avoid cold starts",
      "Optimize code: reduce payload size, use connection reuse, batch operations",
    ],
    agentFix:
      "ShieldOps analyzes Lambda execution traces, identifies timeout root cause (cold start, downstream, code), adjusts timeout and memory settings, enables provisioned concurrency for latency-sensitive functions, and monitors for improvement.",
    agentTime: "45 seconds",
    relatedPages: [
      "fix-rds-connection-limit",
      "fix-alb-5xx-spike",
      "fix-high-p99-latency",
    ],
  },
  {
    slug: "fix-alb-5xx-spike",
    title: "How to Fix ALB 5xx Error Spikes in AWS",
    metaDescription:
      "Troubleshoot AWS Application Load Balancer 5xx error spikes. Diagnose backend health, target group issues, and capacity problems.",
    category: "aws",
    severity: "critical",
    symptoms: [
      "CloudWatch showing spike in HTTPCode_ELB_5XX_Count",
      "End users receiving 502 or 504 errors",
      "ALB access logs showing upstream connect error",
      "Target group health checks failing",
    ],
    causes: [
      "Backend instances or containers unhealthy or overloaded",
      "Target group has no healthy targets",
      "Backend connection timeout exceeded",
      "Deployment in progress causing temporary unhealthy targets",
      "Security group blocking ALB to target communication",
    ],
    manualSteps: [
      "Check target group health: AWS Console > EC2 > Target Groups",
      "Review ALB access logs for specific error codes",
      "Check backend instance/container health and logs",
      "Verify security groups allow ALB to reach targets on the correct port",
      "Check if recent deployment caused the issue",
      "Scale up backends if overloaded",
    ],
    agentFix:
      "ShieldOps correlates ALB 5xx metrics with target health, backend resource usage, and recent deployments, identifies the failing component, and either scales backends, fixes health checks, or rolls back a bad deployment.",
    agentTime: "57 seconds",
    relatedPages: [
      "fix-ec2-instance-unreachable",
      "fix-ecs-task-failure",
      "fix-ingress-502",
    ],
  },
  {
    slug: "fix-ecs-task-failure",
    title: "How to Fix ECS Task Failures in AWS",
    metaDescription:
      "Resolve AWS ECS task failures. Debug container crashes, resource limits, IAM roles, and task placement issues.",
    category: "aws",
    severity: "high",
    symptoms: [
      "ECS tasks showing STOPPED with non-zero exit code",
      "Service events showing has reached a steady state of 0 running tasks",
      "Tasks cycling between PENDING and STOPPED",
      "ECS service unable to reach desired count",
    ],
    causes: [
      "Container crashing on startup (same as CrashLoopBackOff in K8s)",
      "Task role missing required permissions",
      "Insufficient cluster capacity (CPU/memory)",
      "Image pull failure from ECR",
      "Health check failure causing task deregistration",
    ],
    manualSteps: [
      "Check stopped task reason: `aws ecs describe-tasks --tasks <task-arn>`",
      "Review CloudWatch Logs for container output",
      "Verify task definition resource requirements match cluster capacity",
      "Check ECR image availability and permissions",
      "Review task IAM role policies",
      "Check service events: `aws ecs describe-services --services <name>`",
    ],
    agentFix:
      "ShieldOps inspects ECS stopped task reasons, correlates with container logs and cluster capacity, identifies whether the issue is code, permissions, resources, or image, and applies the appropriate fix automatically.",
    agentTime: "48 seconds",
    relatedPages: [
      "fix-pod-crashloopbackoff",
      "fix-alb-5xx-spike",
      "fix-iam-permission-denied",
    ],
  },
  {
    slug: "fix-eks-node-group-scaling",
    title: "How to Fix EKS Node Group Scaling Issues",
    metaDescription:
      "Resolve AWS EKS managed node group scaling failures. Fix autoscaler issues, launch template errors, and capacity problems.",
    category: "aws",
    severity: "high",
    symptoms: [
      "EKS node group stuck at current size despite pending pods",
      "Cluster Autoscaler logs show failed to increase node group size",
      "New nodes launching but failing to join the cluster",
      "Auto Scaling Group showing InsufficientInstanceCapacity errors",
    ],
    causes: [
      "Cluster Autoscaler not installed or misconfigured",
      "ASG launch template using unavailable instance type in the AZ",
      "Node IAM role missing required policies",
      "AWS account limits reached for the instance type",
      "Node bootstrap script failing (userdata error)",
    ],
    manualSteps: [
      "Check Cluster Autoscaler logs: `kubectl logs -n kube-system -l app.kubernetes.io/name=cluster-autoscaler`",
      "Verify ASG in AWS Console: desired vs. actual count",
      "Check EC2 launch errors in ASG activity history",
      "Verify node IAM role has AmazonEKSWorkerNodePolicy, AmazonEKS_CNI_Policy, AmazonEC2ContainerRegistryReadOnly",
      "Try launching the instance type manually to check availability",
      "Review node bootstrap logs: `/var/log/cloud-init-output.log`",
    ],
    agentFix:
      "ShieldOps detects scaling failures, checks ASG capacity, instance availability, IAM roles, and bootstrap health, then fixes the issue by adjusting instance types, correcting IAM policies, or switching to available capacity pools.",
    agentTime: "61 seconds",
    relatedPages: [
      "fix-pending-pods",
      "fix-node-notready",
      "fix-ec2-instance-unreachable",
    ],
  },
  {
    slug: "fix-route53-dns-propagation",
    title: "How to Fix Route53 DNS Propagation Delays",
    metaDescription:
      "Resolve AWS Route53 DNS propagation issues. Debug record changes, TTL settings, and DNS delegation problems.",
    category: "aws",
    severity: "medium",
    symptoms: [
      "DNS changes not reflecting after updating Route53 records",
      "Some users resolving old IP while others see the new one",
      "dig shows different results from different locations",
      "CNAME or alias records not resolving correctly",
    ],
    causes: [
      "High TTL on previous DNS records causing stale caches",
      "DNS resolver caching at ISP or corporate network level",
      "Incorrect hosted zone — record added to wrong zone",
      "NS delegation not properly configured for subdomain",
      "Route53 health check failing, causing failover",
    ],
    manualSteps: [
      "Verify record exists: `aws route53 list-resource-record-sets --hosted-zone-id <id>`",
      "Check TTL values and lower them before planned changes",
      "Test from multiple locations: `dig @8.8.8.8 <domain>` and `dig @1.1.1.1 <domain>`",
      "Verify the correct hosted zone is being used",
      "Check Route53 health checks if using failover routing",
      "Wait for TTL expiry on cached records",
    ],
    agentFix:
      "ShieldOps monitors DNS propagation status across global resolvers, identifies propagation blockers (high TTL, wrong zone, delegation issues), and proactively lowers TTLs before changes and validates propagation completion.",
    agentTime: "36 seconds",
    relatedPages: [
      "fix-dns-resolution-failure",
      "fix-dns-failures-kubernetes",
      "fix-alb-5xx-spike",
    ],
  },
  {
    slug: "fix-iam-permission-denied",
    title: "How to Fix IAM Permission Denied Errors in AWS",
    metaDescription:
      "Resolve AWS IAM Access Denied errors. Debug IAM policies, resource policies, SCPs, and permission boundaries.",
    category: "aws",
    severity: "high",
    symptoms: [
      "AWS API calls returning AccessDenied or UnauthorizedAccess",
      "Application cannot access AWS services despite having an IAM role",
      "Terraform/IaC deploys failing with insufficient permissions",
      "Cross-account assume role failures",
    ],
    causes: [
      "IAM policy missing required actions",
      "Service Control Policy (SCP) blocking at the organization level",
      "Permission boundary restricting effective permissions",
      "Resource-based policy denying access",
      "AssumeRole trust policy not configured for the caller",
    ],
    manualSteps: [
      "Check the error message for the specific action and resource ARN",
      "Use IAM Policy Simulator to test the policy",
      "Review all attached policies: `aws iam list-attached-role-policies --role-name <role>`",
      "Check SCPs in AWS Organizations",
      "Check resource-based policies on the target resource",
      "Enable CloudTrail and search for the denied API call",
    ],
    agentFix:
      "ShieldOps traces the denied API call through IAM policies, SCPs, permission boundaries, and resource policies, identifies the exact deny source, and generates the minimal policy update to grant access while maintaining least privilege.",
    agentTime: "39 seconds",
    relatedPages: [
      "fix-s3-access-denied",
      "fix-unauthorized-api-access",
      "fix-ec2-instance-unreachable",
    ],
  },
  {
    slug: "fix-cloudwatch-alarm-storm",
    title: "How to Fix CloudWatch Alarm Storms",
    metaDescription:
      "Handle AWS CloudWatch alarm storms. Reduce alert noise, configure composite alarms, and prevent alarm fatigue.",
    category: "aws",
    severity: "medium",
    symptoms: [
      "Hundreds of CloudWatch alarms firing simultaneously",
      "PagerDuty/Slack flooded with notifications",
      "On-call engineer overwhelmed with duplicate alerts",
      "Legitimate critical alarms lost in noise",
    ],
    causes: [
      "Single infrastructure event triggering cascading alarms",
      "Alarm thresholds too sensitive (low periods, tight thresholds)",
      "Missing composite alarms to group related alerts",
      "Auto Scaling events triggering metric gaps and false alarms",
      "Deployment causing temporary metric anomalies",
    ],
    manualSteps: [
      "Identify the root event: look for the first alarm that fired",
      "Suppress downstream alarms temporarily",
      "Review alarm thresholds and increase evaluation periods",
      "Create composite alarms for correlated metrics",
      "Add missing data treatment: `treat missing data as not breaching`",
      "Set up alarm suppression during deployment windows",
    ],
    agentFix:
      "ShieldOps correlates concurrent alarms to identify the root event, suppresses cascading noise, fixes the root cause, and recommends composite alarm configurations to prevent future storms.",
    agentTime: "44 seconds",
    relatedPages: [
      "fix-alb-5xx-spike",
      "fix-ec2-instance-unreachable",
      "fix-ecs-task-failure",
    ],
  },
  // ─── Security (10) ─────────────────────────────────────────────────
  {
    slug: "fix-cve-container-image",
    title: "How to Fix CVEs in Container Images",
    metaDescription:
      "Remediate CVE vulnerabilities found in container images. Prioritize by severity, update base images, and automate patching pipelines.",
    category: "security",
    severity: "critical",
    symptoms: [
      "Container scanning tools reporting critical/high CVEs",
      "Admission controller blocking deployments due to vulnerabilities",
      "Security audit flagging unpatched container images",
      "Compliance reports showing vulnerability SLA breaches",
    ],
    causes: [
      "Base image (e.g., Ubuntu, Alpine) not updated to latest patch level",
      "Application dependencies with known vulnerabilities",
      "Using full OS images instead of distroless/minimal images",
      "No automated image rebuild pipeline on CVE disclosure",
      "Pinned to old image tags without regular updates",
    ],
    manualSteps: [
      "Scan the image: `trivy image <image:tag>` or `grype <image:tag>`",
      "Identify which CVEs are in the base image vs. application dependencies",
      "Update the base image in Dockerfile: `FROM node:20-alpine` to latest",
      "Update application dependencies: `npm audit fix` or `pip install --upgrade`",
      "Rebuild and push the patched image",
      "Redeploy affected workloads",
    ],
    agentFix:
      "ShieldOps Security Agent continuously scans running container images, prioritizes CVEs by exploitability and exposure, triggers automated base image updates, rebuilds images through CI/CD, and validates deployments pass admission policies.",
    agentTime: "83 seconds",
    relatedPages: [
      "fix-exposed-secrets-in-logs",
      "fix-compliance-drift",
      "fix-container-escape-attempt",
    ],
  },
  {
    slug: "fix-exposed-secrets-in-logs",
    title: "How to Fix Exposed Secrets in Logs",
    metaDescription:
      "Remediate secrets and credentials exposed in application logs. Implement secret masking, rotate compromised credentials, and prevent recurrence.",
    category: "security",
    severity: "critical",
    symptoms: [
      "API keys or passwords visible in application log output",
      "Secret scanning tools flagging log files",
      "Credentials appearing in centralized logging systems (Splunk, ELK)",
      "Audit finding: sensitive data in CloudWatch Logs",
    ],
    causes: [
      "Application logging full request/response bodies including auth headers",
      "Debug logging enabled in production",
      "Error handlers dumping full stack traces with environment variables",
      "Third-party libraries logging sensitive parameters",
      "Missing log sanitization middleware",
    ],
    manualSteps: [
      "Search logs for known secret patterns: API keys, tokens, passwords",
      "Immediately rotate any exposed credentials",
      "Add log sanitization to redact sensitive fields before logging",
      "Disable debug logging in production",
      "Configure log ingestion to mask patterns matching secrets",
      "Set up automated secret scanning on log streams",
    ],
    agentFix:
      "ShieldOps detects secret patterns in log streams in real-time, immediately rotates compromised credentials, applies log sanitization rules, and deploys webhook-based prevention to block secrets from reaching log storage.",
    agentTime: "62 seconds",
    relatedPages: [
      "fix-api-key-leaked",
      "fix-secret-rotation",
      "fix-cve-container-image",
    ],
  },
  {
    slug: "fix-tls-certificate-expiry",
    title: "How to Fix TLS Certificate Expiry",
    metaDescription:
      "Prevent and remediate TLS certificate expiry. Automate certificate renewal, monitor expiry dates, and handle emergency re-issuance.",
    category: "security",
    severity: "critical",
    symptoms: [
      "Users seeing certificate expired browser warnings",
      "HTTPS connections failing with SSL_ERROR_EXPIRED_CERT",
      "Automated health checks failing due to TLS errors",
      "API clients rejecting responses with certificate verification failed",
    ],
    causes: [
      "Certificate auto-renewal (Let's Encrypt, ACM) silently failing",
      "Manual certificates with no renewal reminders",
      "DNS validation failing for certificate renewal",
      "Certificate stored in wrong path or format",
      "Load balancer serving cached expired certificate",
    ],
    manualSteps: [
      "Check certificate expiry: `echo | openssl s_client -connect <host>:443 2>/dev/null | openssl x509 -noout -dates`",
      "Renew the certificate using your CA or ACME client",
      "Deploy the new certificate to the load balancer or server",
      "Clear any TLS session caches",
      "Verify with: `curl -vI https://<domain>`",
      "Set up monitoring for certificate expiry (30, 14, 7 day alerts)",
    ],
    agentFix:
      "ShieldOps monitors all TLS certificates across infrastructure, triggers automated renewal 30 days before expiry, validates the new certificate, deploys it to all endpoints, and verifies TLS connectivity post-deployment.",
    agentTime: "71 seconds",
    relatedPages: [
      "fix-certificate-expiry-k8s",
      "fix-secret-rotation",
      "fix-alb-5xx-spike",
    ],
  },
  {
    slug: "fix-api-key-leaked",
    title: "How to Fix a Leaked API Key",
    metaDescription:
      "Respond to leaked API keys and credentials. Immediate rotation, exposure assessment, and prevention of future leaks.",
    category: "security",
    severity: "critical",
    symptoms: [
      "GitHub secret scanning alert for exposed API key",
      "Unexpected API usage or billing charges",
      "Third-party notifying of credential exposure",
      "API key found in public repository or paste site",
    ],
    causes: [
      "API key committed to a public Git repository",
      "Key included in client-side code or mobile app",
      "Key shared in plain text via Slack, email, or documentation",
      "Key leaked through CI/CD logs or build artifacts",
      "Developer using production key in local development",
    ],
    manualSteps: [
      "Immediately revoke or rotate the compromised API key",
      "Audit API logs for unauthorized usage during exposure window",
      "Remove the key from the repository using BFG Repo Cleaner or git filter-branch",
      "Deploy the new key to all services that use it",
      "Enable GitHub secret scanning and push protection",
      "Move secrets to a vault (HashiCorp Vault, AWS Secrets Manager)",
    ],
    agentFix:
      "ShieldOps detects leaked keys via integration with secret scanning services, immediately rotates the compromised key, audits usage logs for unauthorized access, deploys the replacement across all dependent services, and configures push protection to prevent recurrence.",
    agentTime: "47 seconds",
    relatedPages: [
      "fix-exposed-secrets-in-logs",
      "fix-secret-rotation",
      "fix-unauthorized-api-access",
    ],
  },
  {
    slug: "fix-unauthorized-api-access",
    title: "How to Fix Unauthorized API Access",
    metaDescription:
      "Respond to unauthorized API access incidents. Investigate access patterns, revoke compromised tokens, and strengthen API security.",
    category: "security",
    severity: "critical",
    symptoms: [
      "API logs showing requests from unknown IP addresses",
      "Spike in 401/403 responses from API endpoints",
      "Data accessed that does not match normal user patterns",
      "Rate limiting triggered by unusual request volumes",
    ],
    causes: [
      "Stolen or leaked API tokens/credentials",
      "Broken authentication — expired tokens still being accepted",
      "Missing authorization checks on API endpoints",
      "BOLA/IDOR vulnerability allowing access to other users' data",
      "API gateway misconfiguration bypassing auth middleware",
    ],
    manualSteps: [
      "Analyze access logs to identify the unauthorized requests",
      "Revoke all potentially compromised tokens",
      "Block suspicious IP addresses at the WAF or API gateway level",
      "Review authentication middleware for bypass vulnerabilities",
      "Audit all API endpoints for proper authorization checks",
      "Implement API key rotation and short-lived JWT tokens",
    ],
    agentFix:
      "ShieldOps detects anomalous API access patterns, correlates with known attack signatures, blocks malicious IPs, revokes compromised tokens, and generates a full incident report with timeline and affected data scope.",
    agentTime: "53 seconds",
    relatedPages: [
      "fix-api-key-leaked",
      "fix-failed-login-brute-force",
      "fix-iam-permission-denied",
    ],
  },
  {
    slug: "fix-failed-login-brute-force",
    title: "How to Fix Failed Login Brute Force Attacks",
    metaDescription:
      "Detect and stop brute force login attacks. Implement rate limiting, account lockout, and CAPTCHA to protect user accounts.",
    category: "security",
    severity: "high",
    symptoms: [
      "Thousands of failed login attempts from single or distributed IPs",
      "Legitimate users locked out of their accounts",
      "Auth service CPU and latency spiking",
      "Security alerts for credential stuffing attempts",
    ],
    causes: [
      "No rate limiting on login endpoints",
      "Credential stuffing using leaked username/password databases",
      "No account lockout or progressive delay mechanism",
      "Bot traffic not detected or blocked",
      "Weak password policy allowing easily guessable passwords",
    ],
    manualSteps: [
      "Identify attacking IPs from auth logs",
      "Block IPs at WAF or firewall level",
      "Enable rate limiting on the login endpoint",
      "Implement account lockout after N failed attempts",
      "Add CAPTCHA after 3 failed attempts",
      "Force password reset for accounts that were targeted",
    ],
    agentFix:
      "ShieldOps detects brute force patterns in real-time, blocks attacking IPs at the edge, enables progressive rate limiting, identifies targeted accounts, forces MFA enrollment for compromised accounts, and generates a threat report.",
    agentTime: "38 seconds",
    relatedPages: [
      "fix-unauthorized-api-access",
      "fix-privilege-escalation",
      "fix-network-scan-detected",
    ],
  },
  {
    slug: "fix-container-escape-attempt",
    title: "How to Fix Container Escape Attempts",
    metaDescription:
      "Respond to container escape attempts. Detect privilege escalation, restrict container capabilities, and harden runtime security.",
    category: "security",
    severity: "critical",
    symptoms: [
      "Falco or runtime security alerts for suspicious syscalls",
      "Container attempting to access host filesystem or devices",
      "Unexpected privileged processes spawning inside containers",
      "Audit logs showing mount of host paths from container context",
    ],
    causes: [
      "Container running as privileged (privileged: true)",
      "Excessive Linux capabilities granted (CAP_SYS_ADMIN)",
      "Host path volumes mounted into containers",
      "Kernel vulnerability exploitable from container namespace",
      "Container image containing known exploit tools",
    ],
    manualSteps: [
      "Isolate the affected container immediately: `kubectl delete pod <name>`",
      "Investigate the container image for malicious content",
      "Review pod security context: check for privileged, capabilities, hostPath",
      "Deploy PodSecurity admission to enforce restricted profile",
      "Update kernel and container runtime to patch known escape CVEs",
      "Implement Falco rules for runtime syscall monitoring",
    ],
    agentFix:
      "ShieldOps detects escape attempts via runtime security integration, immediately isolates the container, captures forensic evidence, identifies the attack vector, applies Pod Security Standards to prevent recurrence, and generates a security incident report.",
    agentTime: "29 seconds",
    relatedPages: [
      "fix-privilege-escalation",
      "fix-cve-container-image",
      "fix-network-scan-detected",
    ],
  },
  {
    slug: "fix-privilege-escalation",
    title: "How to Fix Privilege Escalation Attempts",
    metaDescription:
      "Detect and respond to privilege escalation in cloud and Kubernetes environments. Lock down RBAC, IAM, and container security.",
    category: "security",
    severity: "critical",
    symptoms: [
      "Unauthorized role bindings or IAM policy changes detected",
      "User accessing resources outside their normal scope",
      "sudo or su commands executed in containers",
      "CloudTrail showing unauthorized AssumeRole calls",
    ],
    causes: [
      "Overly permissive RBAC ClusterRoleBindings",
      "IAM policy allowing iam:AttachRolePolicy or sts:AssumeRole broadly",
      "Container running as root with writable host filesystem",
      "Compromised service account with elevated permissions",
      "Misconfigured Kubernetes admission webhooks",
    ],
    manualSteps: [
      "Identify the escalation path from audit logs",
      "Revoke the over-privileged access immediately",
      "Review RBAC bindings: `kubectl get clusterrolebindings -o wide`",
      "Audit IAM policies for escalation paths: `aws iam simulate-principal-policy`",
      "Enforce least-privilege: remove wildcard permissions",
      "Deploy OPA/Gatekeeper policies to prevent privileged containers",
    ],
    agentFix:
      "ShieldOps detects escalation attempts via CloudTrail and Kubernetes audit logs, immediately revokes excessive permissions, locks the compromised identity, traces the full attack path, and deploys preventive OPA policies.",
    agentTime: "34 seconds",
    relatedPages: [
      "fix-container-escape-attempt",
      "fix-unauthorized-api-access",
      "fix-iam-permission-denied",
    ],
  },
  {
    slug: "fix-network-scan-detected",
    title: "How to Fix Network Scan Detection and Response",
    metaDescription:
      "Respond to detected network scans targeting your infrastructure. Investigate reconnaissance, block attackers, and harden network posture.",
    category: "security",
    severity: "high",
    symptoms: [
      "IDS/IPS alerting on port scanning activity",
      "VPC Flow Logs showing connections to many ports from one source",
      "Firewall logs showing sequential port access attempts",
      "Unusual traffic patterns from internal compromised hosts",
    ],
    causes: [
      "External attacker performing reconnaissance",
      "Compromised internal host being used for lateral movement",
      "Legitimate security scanner misconfigured or running unapproved",
      "Malware performing internal network discovery",
      "Red team exercise without proper notification",
    ],
    manualSteps: [
      "Identify the scanning source IP from VPC Flow Logs or IDS alerts",
      "Determine if the source is internal or external",
      "Block external IPs at security group, NACL, or WAF level",
      "Investigate internal sources for compromise",
      "Review what ports/services were discovered",
      "Harden exposed services and close unnecessary ports",
    ],
    agentFix:
      "ShieldOps detects scan patterns from VPC Flow Logs and IDS, automatically blocks the scanning source, checks if any services were exposed, assesses the threat level (external recon vs. lateral movement), and hardens network security groups.",
    agentTime: "41 seconds",
    relatedPages: [
      "fix-container-escape-attempt",
      "fix-failed-login-brute-force",
      "fix-privilege-escalation",
    ],
  },
  {
    slug: "fix-compliance-drift",
    title: "How to Fix Compliance Drift",
    metaDescription:
      "Detect and remediate compliance drift in cloud infrastructure. Restore SOC 2, HIPAA, PCI DSS, and CIS benchmark compliance.",
    category: "security",
    severity: "high",
    symptoms: [
      "Compliance scanner showing new failures against baseline",
      "CIS benchmark score decreasing over time",
      "Audit findings for controls that were previously passing",
      "Security posture score trending downward",
    ],
    causes: [
      "Infrastructure changes made outside of IaC (manual console changes)",
      "New resources deployed without required security controls",
      "Policy exceptions that were never reverted",
      "Compliance rules updated but infrastructure not adjusted",
      "Drift between Terraform state and actual infrastructure",
    ],
    manualSteps: [
      "Run compliance scan: AWS Config rules, ScoutSuite, Prowler",
      "Compare current findings against last known-good baseline",
      "Identify what changed: AWS Config timeline or Terraform plan",
      "Remediate findings: apply missing encryption, logging, access controls",
      "Update IaC to prevent recurrence: `terraform plan` to detect drift",
      "Re-run compliance scan to verify remediation",
    ],
    agentFix:
      "ShieldOps continuously monitors compliance posture, detects drift in real-time, identifies the change that caused drift, automatically remediates by re-applying compliant configurations, and generates evidence for audit documentation.",
    agentTime: "76 seconds",
    relatedPages: [
      "fix-cve-container-image",
      "fix-privilege-escalation",
      "fix-exposed-secrets-in-logs",
    ],
  },
  // ─── Performance (5) ───────────────────────────────────────────────
  {
    slug: "fix-high-p99-latency",
    title: "How to Fix High P99 Latency",
    metaDescription:
      "Diagnose and resolve high P99 tail latency in distributed systems. Identify slow endpoints, database queries, and resource contention.",
    category: "performance",
    severity: "high",
    symptoms: [
      "P99 latency exceeding SLO targets",
      "Small percentage of users experiencing very slow responses",
      "Latency spikes correlating with specific times or events",
      "Error budget burning faster than expected",
    ],
    causes: [
      "Garbage collection pauses (JVM, Go, .NET)",
      "Slow database queries not caught by average latency monitoring",
      "Connection pool contention under load",
      "Noisy neighbor on shared infrastructure",
      "Cold cache misses after deployment or restart",
    ],
    manualSteps: [
      "Review latency distribution histograms, not just averages",
      "Identify slow endpoints: compare P50 vs P99 per route",
      "Check GC logs for long pause events",
      "Profile slow database queries with EXPLAIN ANALYZE",
      "Review connection pool metrics: wait time, active connections",
      "Check for resource contention: CPU throttling, disk I/O wait",
    ],
    agentFix:
      "ShieldOps traces high-latency requests end-to-end, identifies the contributing span (GC, query, pool wait, cache miss), correlates with resource metrics, and applies targeted fixes: pool sizing, query optimization, GC tuning, or cache warming.",
    agentTime: "59 seconds",
    relatedPages: [
      "fix-connection-pool-exhaustion",
      "fix-cpu-throttling",
      "fix-memory-leak",
    ],
  },
  {
    slug: "fix-connection-pool-exhaustion",
    title: "How to Fix Connection Pool Exhaustion",
    metaDescription:
      "Resolve database and HTTP connection pool exhaustion. Fix connection leaks, right-size pools, and prevent pool starvation.",
    category: "performance",
    severity: "critical",
    symptoms: [
      "Application threads blocked waiting for connections",
      "Connection timeout exceptions in application logs",
      "Sudden latency increase across all endpoints",
      "Database showing max connections reached",
    ],
    causes: [
      "Connection leaks — connections not returned to pool after use",
      "Pool size too small for concurrent request volume",
      "Slow queries holding connections for too long",
      "Connection validation overhead causing pool thrashing",
      "Multiple services competing for limited database connections",
    ],
    manualSteps: [
      "Check pool metrics: active, idle, waiting, total connections",
      "Review application code for connection leak patterns (missing finally/close)",
      "Check for slow queries holding connections: `SELECT * FROM pg_stat_activity WHERE state = 'active'`",
      "Increase pool max size if legitimately under-provisioned",
      "Set connection timeout and max lifetime to recycle stale connections",
      "Consider using a connection proxy (PgBouncer, ProxySQL)",
    ],
    agentFix:
      "ShieldOps monitors connection pool metrics across all services, detects leaks by correlating pool usage with transaction patterns, identifies the root cause (leak, sizing, slow query), and applies the fix: patching leaked connections, adjusting pool parameters, or deploying a connection proxy.",
    agentTime: "46 seconds",
    relatedPages: [
      "fix-rds-connection-limit",
      "fix-high-p99-latency",
      "fix-memory-leak",
    ],
  },
  {
    slug: "fix-memory-leak",
    title: "How to Fix Memory Leaks in Production",
    metaDescription:
      "Diagnose and fix memory leaks in production applications. Identify leaking objects, generate heap dumps, and implement fixes.",
    category: "performance",
    severity: "high",
    symptoms: [
      "Memory usage growing steadily over hours/days",
      "Application OOM killed periodically",
      "GC frequency and duration increasing over time",
      "Response times degrading as memory fills up",
    ],
    causes: [
      "Unbounded caches or collections growing without eviction",
      "Event listeners or callbacks not being removed",
      "Static collections accumulating objects",
      "Thread-local variables not cleaned up",
      "Connection or resource handles not properly closed",
    ],
    manualSteps: [
      "Confirm the leak: graph memory usage over 24+ hours",
      "Capture a heap dump: `jmap -dump:live,format=b,file=heap.hprof <pid>`",
      "Analyze with Eclipse MAT or VisualVM to find dominant retainers",
      "For Node.js: use `--inspect` flag and Chrome DevTools memory profiler",
      "Identify the leaking object type and trace allocation sites",
      "Fix the code: add cache eviction, close resources, remove listeners",
    ],
    agentFix:
      "ShieldOps detects memory leak patterns from metrics trending, captures diagnostic data (heap dumps, allocation profiles) before OOM, identifies the leaking component through automated analysis, and provides actionable fix recommendations with code-level pointers.",
    agentTime: "84 seconds",
    relatedPages: [
      "fix-pod-oomkilled",
      "fix-high-p99-latency",
      "fix-cpu-throttling",
    ],
  },
  {
    slug: "fix-cpu-throttling",
    title: "How to Fix CPU Throttling in Containers",
    metaDescription:
      "Resolve CPU throttling in Kubernetes containers. Understand CFS quotas, optimize CPU limits, and eliminate performance degradation.",
    category: "performance",
    severity: "high",
    symptoms: [
      "Application latency spikes correlating with CPU throttling metrics",
      "container_cpu_cfs_throttled_periods_total increasing",
      "Pods using less CPU than their limit but still throttled",
      "Inconsistent response times despite low average CPU usage",
    ],
    causes: [
      "CPU limits set too low for burst workloads",
      "CFS scheduler quota exhausted within the period",
      "Multi-threaded applications hitting per-core limits",
      "CPU requests and limits set to the same value (no burstable QoS)",
      "Noisy neighbor consuming shared CPU on the node",
    ],
    manualSteps: [
      "Check throttling: `kubectl top pod <name>` and Prometheus container_cpu_cfs_throttled_seconds_total",
      "Review CPU limits: `kubectl get pod <name> -o yaml | grep -A 2 limits`",
      "Compare actual CPU usage vs. limits — if usage is near limit, increase it",
      "Consider removing CPU limits (keep only requests) for non-batch workloads",
      "Ensure node has sufficient CPU capacity",
      "For Java apps, align JVM thread count with available CPU cores",
    ],
    agentFix:
      "ShieldOps correlates throttling metrics with latency impact, identifies whether the root cause is tight limits, burst patterns, or noisy neighbors, and automatically adjusts CPU limits based on historical usage patterns to eliminate throttling while maintaining cluster efficiency.",
    agentTime: "42 seconds",
    relatedPages: [
      "fix-pod-oomkilled",
      "fix-high-p99-latency",
      "fix-hpa-not-scaling",
    ],
  },
  {
    slug: "fix-disk-io-saturation",
    title: "How to Fix Disk I/O Saturation",
    metaDescription:
      "Resolve disk I/O saturation causing application slowdowns. Diagnose IOPS limits, optimize I/O patterns, and right-size storage.",
    category: "performance",
    severity: "high",
    symptoms: [
      "Application read/write operations extremely slow",
      "iowait percentage high in system metrics",
      "AWS EBS BurstBalance at 0% or IOPS at provisioned limit",
      "Database query latency correlated with disk metrics",
    ],
    causes: [
      "EBS volume IOPS limit reached (gp2 burst exhausted, gp3 baseline exceeded)",
      "Too many concurrent I/O operations (database + logging + application)",
      "Write-heavy workload on storage optimized for reads",
      "Log volume filling disk causing write delays",
      "Filesystem fragmentation on long-running volumes",
    ],
    manualSteps: [
      "Check disk metrics: `iostat -x 1` on the node",
      "For AWS: check CloudWatch VolumeReadOps, VolumeWriteOps, BurstBalance",
      "Identify I/O-heavy processes: `iotop` on the node",
      "Upgrade EBS volume type (gp2 to gp3, or provision higher IOPS)",
      "Offload logging to a separate volume or remote logging service",
      "Optimize database I/O: add indexes, tune buffer pool, enable compression",
    ],
    agentFix:
      "ShieldOps monitors disk I/O metrics across nodes, detects saturation before it impacts applications, identifies the I/O-heavy workload, and either upgrades storage performance (EBS type, IOPS), offloads workloads, or optimizes I/O patterns.",
    agentTime: "51 seconds",
    relatedPages: [
      "fix-high-p99-latency",
      "fix-evicted-pods",
      "fix-rds-connection-limit",
    ],
  },
  // ─── Networking (5) ────────────────────────────────────────────────
  {
    slug: "fix-dns-resolution-failure",
    title: "How to Fix DNS Resolution Failures",
    metaDescription:
      "Troubleshoot DNS resolution failures across cloud and on-premise infrastructure. Fix resolvers, forwarders, and DNS misconfigurations.",
    category: "networking",
    severity: "critical",
    symptoms: [
      "Applications failing with name resolution errors",
      "dig/nslookup returning SERVFAIL or NXDOMAIN unexpectedly",
      "Intermittent DNS failures affecting subset of hosts",
      "DNS-dependent health checks failing",
    ],
    causes: [
      "DNS resolver (e.g., Route53 Resolver, VPC DHCP options) misconfigured",
      "Upstream DNS server overloaded or unreachable",
      "DNS zone delegation broken",
      "Split-horizon DNS returning wrong records for private/public zone",
      "Firewall blocking DNS traffic (UDP/TCP 53)",
    ],
    manualSteps: [
      "Test resolution from the affected host: `dig <domain>` and `dig @<specific-resolver> <domain>`",
      "Check resolver configuration: `/etc/resolv.conf` or DHCP options",
      "Verify DNS zone exists and has correct records",
      "Test upstream forwarders: `dig @<upstream> <domain>`",
      "Check firewall rules for DNS traffic",
      "Review DNS query logs for error patterns",
    ],
    agentFix:
      "ShieldOps detects DNS resolution failures across the fleet, traces the resolution path, identifies the failing component (resolver, forwarder, zone, firewall), and applies the fix while monitoring resolution success rates.",
    agentTime: "43 seconds",
    relatedPages: [
      "fix-dns-failures-kubernetes",
      "fix-coredns-timeout",
      "fix-route53-dns-propagation",
    ],
  },
  {
    slug: "fix-load-balancer-health-check",
    title: "How to Fix Load Balancer Health Check Failures",
    metaDescription:
      "Troubleshoot load balancer health check failures. Fix backend health, check configuration, and restore traffic routing.",
    category: "networking",
    severity: "high",
    symptoms: [
      "Load balancer marking healthy backends as unhealthy",
      "Traffic not reaching certain backend instances",
      "503 Service Unavailable during health check failures",
      "Flapping health status on backends",
    ],
    causes: [
      "Health check path returning non-200 status code",
      "Health check timeout too short for application response time",
      "Security group blocking health check source IPs",
      "Health check port different from application port",
      "Application not listening on the expected interface (bound to localhost only)",
    ],
    manualSteps: [
      "Check health check configuration: path, port, protocol, thresholds",
      "Test the health check endpoint from the backend: `curl -v http://localhost:<port><path>`",
      "Verify security groups allow health check traffic from LB CIDR",
      "Check application is binding to 0.0.0.0 not 127.0.0.1",
      "Increase health check timeout and unhealthy threshold",
      "Review load balancer access logs for health check responses",
    ],
    agentFix:
      "ShieldOps verifies the entire health check chain — endpoint response, security groups, port binding, and timing — identifies the misconfiguration, and fixes it while ensuring zero-downtime by validating before applying changes.",
    agentTime: "37 seconds",
    relatedPages: [
      "fix-alb-5xx-spike",
      "fix-ingress-502",
      "fix-tcp-connection-timeout",
    ],
  },
  {
    slug: "fix-tcp-connection-timeout",
    title: "How to Fix TCP Connection Timeouts",
    metaDescription:
      "Resolve TCP connection timeout issues in distributed systems. Diagnose network path, MTU, and connection establishment failures.",
    category: "networking",
    severity: "high",
    symptoms: [
      "Application logs showing connection timed out errors",
      "TCP SYN packets sent but no SYN-ACK received",
      "Intermittent connectivity failures between services",
      "Connection timeouts only to specific destinations",
    ],
    causes: [
      "Firewall or security group blocking the port",
      "Target service not listening on the expected port",
      "Network path issue — routing, NAT, or VPN tunnel down",
      "TCP connection backlog full on target server",
      "MTU mismatch causing packet fragmentation and drops",
    ],
    manualSteps: [
      "Test connectivity: `telnet <host> <port>` or `nc -zv <host> <port>`",
      "Trace the path: `traceroute <host>` to find where packets stop",
      "Check security groups and firewall rules for both source and destination",
      "Verify target service is running and listening: `netstat -tlnp` on the target",
      "Check for MTU issues: `ping -M do -s 1472 <host>`",
      "Review VPN or transit gateway status for cross-VPC/cross-region traffic",
    ],
    agentFix:
      "ShieldOps traces the network path from source to destination, checks every hop for blockages (security groups, NACLs, route tables, VPN), identifies the failing component, and remediates by fixing rules, restarting tunnels, or correcting routing.",
    agentTime: "48 seconds",
    relatedPages: [
      "fix-dns-resolution-failure",
      "fix-load-balancer-health-check",
      "fix-rate-limiting",
    ],
  },
  {
    slug: "fix-rate-limiting",
    title: "How to Fix Rate Limiting Issues",
    metaDescription:
      "Resolve rate limiting causing service disruptions. Configure rate limits correctly, implement backoff, and handle burst traffic.",
    category: "networking",
    severity: "medium",
    symptoms: [
      "API returning 429 Too Many Requests responses",
      "Legitimate traffic being rejected during peak hours",
      "Third-party API calls failing due to rate limits",
      "Cascading failures as retries amplify load",
    ],
    causes: [
      "Rate limit thresholds too aggressive for legitimate traffic patterns",
      "No distinction between authenticated and anonymous rate limits",
      "Retry storms from clients without exponential backoff",
      "Single service consuming disproportionate share of shared rate limit",
      "Rate limiter not accounting for burst traffic patterns",
    ],
    manualSteps: [
      "Identify which rate limit is being hit from response headers (X-RateLimit-*)",
      "Analyze traffic patterns to determine appropriate limits",
      "Implement client-side exponential backoff with jitter",
      "Configure per-customer or per-service rate limits instead of global",
      "Add burst allowance (token bucket) to handle spikes",
      "For third-party APIs, implement request queuing and prioritization",
    ],
    agentFix:
      "ShieldOps analyzes rate limit hit patterns, identifies whether limits are misconfigured or traffic is genuinely excessive, adjusts rate limit thresholds based on traffic analysis, and deploys client-side backoff configuration to prevent retry storms.",
    agentTime: "34 seconds",
    relatedPages: [
      "fix-high-p99-latency",
      "fix-circuit-breaker-open",
      "fix-alb-5xx-spike",
    ],
  },
  {
    slug: "fix-circuit-breaker-open",
    title: "How to Fix Circuit Breaker Open",
    metaDescription:
      "Resolve open circuit breakers in microservice architectures. Restore service communication, tune thresholds, and prevent cascading failures.",
    category: "networking",
    severity: "high",
    symptoms: [
      "Service returning fallback responses or errors immediately",
      "Circuit breaker metrics showing OPEN state",
      "Downstream service recovered but upstream still failing",
      "Half-open probes failing, keeping circuit open",
    ],
    causes: [
      "Downstream service had a transient failure that triggered the breaker",
      "Circuit breaker thresholds too sensitive (low error count triggers open)",
      "Half-open recovery probe hitting an unhealthy endpoint",
      "Downstream returned errors that should not count as failures (e.g., 404)",
      "Timeout configuration mismatch between breaker and downstream",
    ],
    manualSteps: [
      "Check circuit breaker state in service dashboard or metrics",
      "Verify the downstream service has actually recovered",
      "Manually close the circuit breaker if the service supports it",
      "Review circuit breaker configuration: error threshold, timeout, half-open probes",
      "Adjust which error types count as failures (exclude 4xx client errors)",
      "Tune timeout durations to match downstream SLAs",
    ],
    agentFix:
      "ShieldOps monitors circuit breaker states across the service mesh, verifies downstream health before resetting breakers, automatically adjusts thresholds based on historical failure patterns, and prevents cascading failures by coordinating recovery across dependent services.",
    agentTime: "39 seconds",
    relatedPages: [
      "fix-rate-limiting",
      "fix-high-p99-latency",
      "fix-tcp-connection-timeout",
    ],
  },
];

export const SEO_CATEGORIES: Record<SEOCategory, { label: string; description: string }> = {
  kubernetes: {
    label: "Kubernetes",
    description: "Troubleshoot Kubernetes cluster, pod, and workload issues",
  },
  aws: {
    label: "AWS",
    description: "Resolve AWS service failures and misconfigurations",
  },
  security: {
    label: "Security",
    description: "Respond to security incidents and compliance issues",
  },
  performance: {
    label: "Performance",
    description: "Fix latency, resource, and throughput problems",
  },
  networking: {
    label: "Networking",
    description: "Diagnose DNS, connectivity, and routing failures",
  },
};

export function getSEOPageBySlug(slug: string): SEOPage | undefined {
  return SEO_PAGES.find((p) => p.slug === slug);
}

export function getSEOPagesByCategory(category: SEOCategory): SEOPage[] {
  return SEO_PAGES.filter((p) => p.category === category);
}
