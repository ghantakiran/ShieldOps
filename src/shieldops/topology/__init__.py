"""Service dependency topology for ShieldOps.

Auto-discovers service topology from OpenTelemetry traces,
Kubernetes service discovery, and manual config declarations.
"""

from shieldops.topology.graph import (
    DependencyView,
    ServiceEdge,
    ServiceGraphBuilder,
    ServiceMap,
    ServiceNode,
)

__all__ = [
    "DependencyView",
    "ServiceEdge",
    "ServiceGraphBuilder",
    "ServiceMap",
    "ServiceNode",
]
