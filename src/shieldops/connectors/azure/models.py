"""Pydantic v2 models for Azure resource representations."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class AzureVM(BaseModel):
    """Azure Virtual Machine."""

    name: str
    resource_group: str
    location: str
    vm_size: str = ""
    status: str = ""  # running / stopped / deallocated
    os_type: str = ""
    private_ip: str | None = None
    public_ip: str | None = None
    tags: dict[str, str] = Field(default_factory=dict)


class AKSNodePool(BaseModel):
    """AKS node pool within a managed cluster."""

    name: str
    vm_size: str = ""
    node_count: int = 0
    min_count: int = 0
    max_count: int = 0
    mode: str = ""  # System / User
    os_type: str = ""


class AKSCluster(BaseModel):
    """Azure Kubernetes Service managed cluster."""

    name: str
    resource_group: str
    location: str
    kubernetes_version: str = ""
    node_count: int = 0
    status: str = ""
    fqdn: str = ""
    node_pools: list[AKSNodePool] = Field(default_factory=list)


class AzureSQLServer(BaseModel):
    """Azure SQL logical server."""

    name: str
    resource_group: str
    location: str
    version: str = ""
    state: str = ""
    fqdn: str = ""
    admin_login: str = ""


class AzureMetric(BaseModel):
    """Azure Monitor metric time series."""

    name: str
    unit: str = ""
    timestamps: list[datetime] = Field(default_factory=list)
    values: list[float] = Field(default_factory=list)
    resource_id: str = ""
