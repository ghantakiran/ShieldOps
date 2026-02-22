"""API routes for plugin management."""

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from shieldops.plugins.base import PluginType
from shieldops.plugins.loader import PluginLoader
from shieldops.plugins.registry import PluginRegistry

router = APIRouter()

_registry: PluginRegistry | None = None
_loader: PluginLoader | None = None


def set_plugin_registry(registry: PluginRegistry, loader: PluginLoader | None = None) -> None:
    global _registry, _loader
    _registry = registry
    _loader = loader


def _get_registry() -> PluginRegistry:
    if _registry is None:
        raise HTTPException(status_code=503, detail="Plugin registry not initialized")
    return _registry


class InstallPluginRequest(BaseModel):
    package_name: str
    config: dict[str, Any] | None = None


@router.get("/plugins")
async def list_plugins(
    plugin_type: str | None = None,
    enabled_only: bool = False,
) -> dict[str, Any]:
    """List all installed plugins."""
    registry = _get_registry()

    ptype = PluginType(plugin_type) if plugin_type else None
    plugins = registry.list_plugins(plugin_type=ptype, enabled_only=enabled_only)

    return {
        "plugins": [p.model_dump() for p in plugins],
        "count": len(plugins),
    }


@router.get("/plugins/{name}")
async def get_plugin(name: str) -> dict[str, Any]:
    """Get plugin details."""
    registry = _get_registry()
    status = registry.get_status(name)
    if status is None:
        raise HTTPException(status_code=404, detail=f"Plugin '{name}' not found")

    plugin = registry.get_plugin(name)
    result = status.model_dump()
    if plugin:
        result["health"] = plugin.health_check()
    return result


@router.post("/plugins/install")
async def install_plugin(body: InstallPluginRequest) -> dict[str, Any]:
    """Install a plugin from a Python package."""
    if _loader is None:
        raise HTTPException(status_code=503, detail="Plugin loader not initialized")

    name = await _loader.load_from_package(body.package_name, config=body.config)
    if name is None:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to load plugin from package '{body.package_name}'",
        )

    registry = _get_registry()
    status = registry.get_status(name)
    return {"installed": True, "plugin": status.model_dump() if status else {"name": name}}


@router.delete("/plugins/{name}")
async def uninstall_plugin(name: str) -> dict[str, Any]:
    """Uninstall a plugin."""
    registry = _get_registry()
    removed = await registry.unregister(name)
    if not removed:
        raise HTTPException(status_code=404, detail=f"Plugin '{name}' not found")
    return {"uninstalled": True, "name": name}


@router.post("/plugins/{name}/enable")
async def enable_plugin(name: str) -> dict[str, Any]:
    """Enable a disabled plugin."""
    registry = _get_registry()
    success = await registry.enable(name)
    if not success:
        raise HTTPException(status_code=400, detail=f"Failed to enable plugin '{name}'")
    status = registry.get_status(name)
    return {"enabled": True, "plugin": status.model_dump() if status else {"name": name}}


@router.post("/plugins/{name}/disable")
async def disable_plugin(name: str) -> dict[str, Any]:
    """Disable an enabled plugin."""
    registry = _get_registry()
    success = await registry.disable(name)
    if not success:
        raise HTTPException(status_code=400, detail=f"Failed to disable plugin '{name}'")
    status = registry.get_status(name)
    return {"disabled": True, "plugin": status.model_dump() if status else {"name": name}}
