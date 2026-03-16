"""Plugin base class and plugin chain for the GA4GH ServiceInfo Sidecar."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class SidecarPlugin(ABC):
    """Base class for sidecar plugins.

    Plugins can enrich the /service-info response with service-specific
    metadata. They are executed in order after the deep merge.
    """

    @abstractmethod
    def name(self) -> str:
        """Human-readable plugin name."""
        ...

    async def on_startup(self, config: dict[str, Any]) -> None:
        """Called once when the sidecar starts. Use for initialization."""
        pass

    async def enrich_service_info(self, response: dict[str, Any]) -> dict[str, Any]:
        """Modify the /service-info response before returning to client.

        The response dict has already been merged (sidecar + backend).
        Plugins can add, modify, or remove fields.

        Args:
            response: The merged /service-info response.

        Returns:
            The enriched response. Must return a dict.
        """
        return response

    def __repr__(self) -> str:
        return f"<Plugin: {self.name()}>"


class PluginChain:
    """Manages an ordered list of plugins."""

    def __init__(self) -> None:
        self._plugins: list[SidecarPlugin] = []

    @property
    def plugins(self) -> list[SidecarPlugin]:
        return list(self._plugins)

    def add(self, plugin: SidecarPlugin) -> None:
        self._plugins.append(plugin)

    async def startup_all(self, plugin_configs: dict[str, dict[str, Any]]) -> None:
        """Call on_startup for all plugins."""
        for plugin in self._plugins:
            config = plugin_configs.get(plugin.name(), {})
            await plugin.on_startup(config)

    async def enrich(self, response: dict[str, Any]) -> dict[str, Any]:
        """Run all plugins in order to enrich the response."""
        for plugin in self._plugins:
            response = await plugin.enrich_service_info(response)
        return response
