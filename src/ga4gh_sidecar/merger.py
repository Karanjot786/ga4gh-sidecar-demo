"""Deep merge algorithm for /service-info responses.

The sidecar config and the backend's /service-info response need to be combined
into a single response. This module defines the precedence rules and the merge logic.

Precedence:
  - Sidecar wins for identity fields (id, name, organization, contactUrl, etc.)
  - Backend wins for capability fields (storage, workflow_type_versions, etc.)
  - Arrays are concatenated and deduplicated
  - Nested dicts are recursively merged
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# Fields where the sidecar operator's config takes priority
SIDECAR_AUTHORITATIVE: set[str] = {
    "id",
    "name",
    "organization",
    "contactUrl",
    "documentationUrl",
    "environment",
    "description",
}

# Fields where the backend's live state takes priority
BACKEND_AUTHORITATIVE: set[str] = {
    "storage",
    "workflow_type_versions",
    "supported_wes_versions",
    "workflow_engine_versions",
}


def merge_service_info(
    sidecar_config: dict[str, Any],
    backend_response: dict[str, Any],
) -> dict[str, Any]:
    """Merge sidecar config with backend /service-info response.

    Uses explicit precedence rules rather than a generic deep merge
    so the behavior is predictable and easy to reason about.
    """
    merged: dict[str, Any] = {}
    all_keys = set(sidecar_config.keys()) | set(backend_response.keys())

    for key in all_keys:
        sc_val = sidecar_config.get(key)
        be_val = backend_response.get(key)

        if key in SIDECAR_AUTHORITATIVE:
            merged[key] = sc_val if sc_val is not None else be_val
        elif key in BACKEND_AUTHORITATIVE:
            merged[key] = be_val if be_val is not None else sc_val
        elif isinstance(sc_val, dict) and isinstance(be_val, dict):
            # Recursive merge for nested objects (e.g. type, extension)
            merged[key] = _deep_merge_dicts(sc_val, be_val)
        elif isinstance(sc_val, list) and isinstance(be_val, list):
            # Concatenate and deduplicate arrays
            merged[key] = _merge_lists(sc_val, be_val)
        elif sc_val is not None:
            merged[key] = sc_val
        else:
            merged[key] = be_val

    return merged


def _deep_merge_dicts(
    base: dict[str, Any], override: dict[str, Any]
) -> dict[str, Any]:
    """Recursively merge two dicts. Override values take precedence for scalars."""
    result = dict(base)
    for key, val in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(val, dict):
            result[key] = _deep_merge_dicts(result[key], val)
        elif key in result and isinstance(result[key], list) and isinstance(val, list):
            result[key] = _merge_lists(result[key], val)
        else:
            result[key] = val
    return result


def _merge_lists(a: list, b: list) -> list:
    """Concatenate two lists, deduplicating where possible."""
    seen = set()
    merged = []
    for item in a + b:
        # For unhashable items (dicts), just append
        try:
            if item not in seen:
                seen.add(item)
                merged.append(item)
        except TypeError:
            merged.append(item)
    return merged


class ServiceInfoCache:
    """Manages the cached, merged /service-info response.

    Polls the backend on an interval, merges with sidecar config,
    runs plugins, and stores the result in memory.
    """

    def __init__(
        self,
        sidecar_config: dict[str, Any],
        backend_url: str,
        poll_interval: int = 30,
        backend_timeout: int = 5,
        fallback: str = "serve_config_only",
    ):
        self._sidecar_config = sidecar_config
        self._backend_url = backend_url.rstrip("/")
        self._poll_interval = poll_interval
        self._backend_timeout = backend_timeout
        self._fallback = fallback

        # The cached response served to clients
        self._cached: dict[str, Any] = dict(sidecar_config)
        self._last_backend_response: dict[str, Any] | None = None
        self._last_poll: datetime | None = None
        self._backend_healthy: bool = False
        self._poll_task: asyncio.Task | None = None
        self._plugins: list = []

    @property
    def cached_response(self) -> dict[str, Any]:
        return dict(self._cached)

    @property
    def is_backend_healthy(self) -> bool:
        return self._backend_healthy

    def set_plugins(self, plugins: list) -> None:
        """Set the plugin chain for enriching responses."""
        self._plugins = plugins

    async def start_polling(self) -> None:
        """Start the background polling loop."""
        # Do one immediate poll
        await self._poll_backend()
        # Then schedule periodic polls
        self._poll_task = asyncio.create_task(self._poll_loop())

    async def stop_polling(self) -> None:
        """Stop the background polling loop."""
        if self._poll_task:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass

    async def _poll_loop(self) -> None:
        """Continuously poll the backend."""
        while True:
            await asyncio.sleep(self._poll_interval)
            await self._poll_backend()

    async def _poll_backend(self) -> None:
        """Fetch backend /service-info, merge, and update cache."""
        try:
            async with httpx.AsyncClient(timeout=self._backend_timeout) as client:
                resp = await client.get(f"{self._backend_url}/service-info")
                resp.raise_for_status()
                backend_data = resp.json()

            self._last_backend_response = backend_data
            self._backend_healthy = True
            self._last_poll = datetime.now(timezone.utc)

            # Merge sidecar config with backend response
            merged = merge_service_info(self._sidecar_config, backend_data)

            # Run plugins
            for plugin in self._plugins:
                merged = await plugin.enrich_service_info(merged)

            self._cached = merged
            logger.info("Polled backend /service-info successfully, cache updated.")

        except (httpx.HTTPError, httpx.ConnectError, Exception) as e:
            self._backend_healthy = False
            logger.warning(f"Failed to poll backend /service-info: {e}")

            if self._fallback == "serve_config_only":
                # Use sidecar config only, still run plugins
                merged = dict(self._sidecar_config)
                for plugin in self._plugins:
                    merged = await plugin.enrich_service_info(merged)
                self._cached = merged
