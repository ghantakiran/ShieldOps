"""Pydantic v2 models for GCP resource representations."""

from datetime import datetime

from pydantic import BaseModel, Field


class GCPInstance(BaseModel):
    """Compute Engine VM instance."""

    instance_id: str
    name: str
    zone: str
    machine_type: str
    status: str
    internal_ip: str | None = None
    external_ip: str | None = None
    labels: dict[str, str] = Field(default_factory=dict)
    created_at: datetime | None = None
    network_tags: list[str] = Field(default_factory=list)


class GKECluster(BaseModel):
    """Google Kubernetes Engine cluster."""

    cluster_id: str
    name: str
    location: str
    status: str
    node_count: int = 0
    master_version: str = ""
    node_version: str = ""
    endpoint: str = ""
    network: str = ""
    subnetwork: str = ""


class GKENodePool(BaseModel):
    """GKE node pool within a cluster."""

    pool_id: str
    name: str
    cluster_name: str
    machine_type: str = ""
    node_count: int = 0
    min_nodes: int = 0
    max_nodes: int = 0
    status: str = ""
    autoscaling_enabled: bool = False


class CloudSQLInstance(BaseModel):
    """Cloud SQL database instance."""

    instance_name: str
    database_version: str = ""
    tier: str = ""
    status: str = ""
    region: str = ""
    storage_size_gb: float = 0.0
    storage_used_gb: float = 0.0
    ip_addresses: list[dict[str, str]] = Field(default_factory=list)
    backup_enabled: bool = False
    ha_enabled: bool = False


class GCPMetricPoint(BaseModel):
    """A single metric data point."""

    timestamp: datetime
    value: float


class GCPMetric(BaseModel):
    """Cloud Monitoring metric time series."""

    metric_type: str
    resource_type: str
    resource_labels: dict[str, str] = Field(default_factory=dict)
    points: list[tuple[datetime, float]] = Field(default_factory=list)
