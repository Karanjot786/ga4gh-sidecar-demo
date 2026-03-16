"""WES plugin — injects workflow type versions into /service-info."""

from __future__ import annotations

import logging
from typing import Any

from ga4gh_sidecar.plugins.base import SidecarPlugin

logger = logging.getLogger(__name__)


class WESPlugin(SidecarPlugin):
    """Enriches /service-info with WES-specific metadata.

    Ensures the response includes `workflow_type_versions` and
    `supported_wes_versions` fields.
    """

    def __init__(self) -> None:
        self._default_workflow_types: dict[str, dict[str, list[str]]] = {
            "CWL": {"versions": ["1.0", "1.1", "1.2"]},
            "WDL": {"versions": ["1.0", "1.1"]},
        }
        self._default_wes_versions: list[str] = ["1.0.0", "1.1.0"]

    def name(self) -> str:
        return "wes"

    async def on_startup(self, config: dict[str, Any]) -> None:
        if "workflow_type_versions" in config:
            self._default_workflow_types = config["workflow_type_versions"]
        if "supported_wes_versions" in config:
            self._default_wes_versions = config["supported_wes_versions"]

    async def enrich_service_info(self, response: dict[str, Any]) -> dict[str, Any]:
        if "workflow_type_versions" not in response:
            response["workflow_type_versions"] = self._default_workflow_types

        if "supported_wes_versions" not in response:
            response["supported_wes_versions"] = self._default_wes_versions

        # Set type to WES
        if "type" in response and isinstance(response["type"], dict):
            response["type"]["artifact"] = "wes"
            if "group" not in response["type"]:
                response["type"]["group"] = "org.ga4gh"

        return response
