"""Root conftest — stubs for optional/heavy dependencies not installed in test env."""

import sys
from types import ModuleType
from unittest.mock import MagicMock

# Stub kubernetes_asyncio before any module imports it.
# The real package isn't installed in the dev/test virtualenv; without this stub,
# importing KubernetesConnector (and anything that transitively touches it) would
# raise ModuleNotFoundError.
_k8s_mod = ModuleType("kubernetes_asyncio")
_k8s_client = ModuleType("kubernetes_asyncio.client")
_k8s_config = ModuleType("kubernetes_asyncio.config")

# Provide the attributes that connector.py actually uses
_k8s_client.CoreV1Api = MagicMock()
_k8s_client.AppsV1Api = MagicMock()
_k8s_client.ApiException = type("ApiException", (Exception,), {})
_k8s_client.ApiClient = MagicMock()
_k8s_config.load_kube_config = MagicMock()
_k8s_config.load_incluster_config = MagicMock()

_k8s_mod.client = _k8s_client
_k8s_mod.config = _k8s_config

sys.modules["kubernetes_asyncio"] = _k8s_mod
sys.modules["kubernetes_asyncio.client"] = _k8s_client
sys.modules["kubernetes_asyncio.config"] = _k8s_config
