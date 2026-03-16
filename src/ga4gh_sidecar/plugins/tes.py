"""TES plugin — injects storage protocols into /service-info."""

from __future__ import annotations

import logging
from typing import Any

from ga4gh_sidecar.plugins.base import SidecarPlugin

logger = logging.getLogger(__name__)


class TESPlugin(SidecarPlugin):
    """Enriches /service-info with TES-specific metadata.

    Ensures the response includes a `storage` array listing the
    file transfer protocols this TES instance supports.
    """

    def __init__(self) -> None:
        self._default_protocols: list[str] = ["s3", "gs", "file", "http"]
        self._override: list[str] | None = None

    def name(self) -> str:
        return "tes"

    async def on_startup(self, config: dict[str, Any]) -> None:
        if "override_protocols" in config:
            self._override = config["override_protocols"]
            logger.info(f"TES plugin: using override protocols {self._override}")

    async def enrich_service_info(self, response: dict[str, Any]) -> dict[str, Any]:
        # If operator specified explicit protocols, use those
        if self._override is not None:
            response["storage"] = self._override
        elif "storage" not in response:
            # Backend didn't provide storage info, use defaults
            response["storage"] = self._default_protocols

        # Make sure the type is set correctly
        if "type" in response and isinstance(response["type"], dict):
            response["type"]["artifact"] = "tes"
            if "group" not in response["type"]:
                response["type"]["group"] = "org.ga4gh"

        return response
