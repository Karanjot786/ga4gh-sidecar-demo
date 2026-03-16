"""Tests for the plugin system."""

import pytest

from ga4gh_sidecar.plugins.base import PluginChain, SidecarPlugin
from ga4gh_sidecar.plugins.tes import TESPlugin
from ga4gh_sidecar.plugins.wes import WESPlugin


class TestTESPlugin:
    """Test the TES storage protocol plugin."""

    @pytest.mark.asyncio
    async def test_injects_default_storage(self):
        """TES plugin should add default storage protocols if missing."""
        plugin = TESPlugin()
        await plugin.on_startup({})

        response = {"id": "org.test", "type": {"group": "org.ga4gh"}}
        result = await plugin.enrich_service_info(response)

        assert "storage" in result
        assert "s3" in result["storage"]
        assert "gs" in result["storage"]

    @pytest.mark.asyncio
    async def test_preserves_existing_storage(self):
        """If backend already provided storage, TES plugin should not override."""
        plugin = TESPlugin()
        await plugin.on_startup({})

        response = {
            "id": "org.test",
            "type": {"group": "org.ga4gh"},
            "storage": ["s3", "ftp"],
        }
        result = await plugin.enrich_service_info(response)

        assert result["storage"] == ["s3", "ftp"]

    @pytest.mark.asyncio
    async def test_override_protocols_from_config(self):
        """Operator can override protocols via plugin config."""
        plugin = TESPlugin()
        await plugin.on_startup({"override_protocols": ["gs", "http"]})

        response = {
            "id": "org.test",
            "type": {"group": "org.ga4gh"},
            "storage": ["s3"],
        }
        result = await plugin.enrich_service_info(response)

        assert result["storage"] == ["gs", "http"]

    @pytest.mark.asyncio
    async def test_sets_artifact_to_tes(self):
        """TES plugin should set type.artifact to 'tes'."""
        plugin = TESPlugin()
        await plugin.on_startup({})

        response = {"type": {"group": "org.ga4gh", "version": "1.1.0"}}
        result = await plugin.enrich_service_info(response)

        assert result["type"]["artifact"] == "tes"


class TestWESPlugin:
    """Test the WES workflow type versions plugin."""

    @pytest.mark.asyncio
    async def test_injects_default_workflow_types(self):
        """WES plugin should add default workflow types if missing."""
        plugin = WESPlugin()
        await plugin.on_startup({})

        response = {"id": "org.test", "type": {"group": "org.ga4gh"}}
        result = await plugin.enrich_service_info(response)

        assert "workflow_type_versions" in result
        assert "CWL" in result["workflow_type_versions"]
        assert "WDL" in result["workflow_type_versions"]

    @pytest.mark.asyncio
    async def test_injects_supported_wes_versions(self):
        """WES plugin should add supported WES versions."""
        plugin = WESPlugin()
        await plugin.on_startup({})

        response = {"id": "org.test", "type": {"group": "org.ga4gh"}}
        result = await plugin.enrich_service_info(response)

        assert "supported_wes_versions" in result
        assert "1.0.0" in result["supported_wes_versions"]

    @pytest.mark.asyncio
    async def test_sets_artifact_to_wes(self):
        """WES plugin should set type.artifact to 'wes'."""
        plugin = WESPlugin()
        await plugin.on_startup({})

        response = {"type": {"group": "org.ga4gh", "version": "1.1.0"}}
        result = await plugin.enrich_service_info(response)

        assert result["type"]["artifact"] == "wes"


class TestPluginChain:
    """Test the plugin chain execution."""

    @pytest.mark.asyncio
    async def test_chain_executes_in_order(self):
        """Plugins should execute in the order they were added."""
        execution_order = []

        class PluginA(SidecarPlugin):
            def name(self) -> str:
                return "a"

            async def enrich_service_info(self, response):
                execution_order.append("a")
                response["plugin_a"] = True
                return response

        class PluginB(SidecarPlugin):
            def name(self) -> str:
                return "b"

            async def enrich_service_info(self, response):
                execution_order.append("b")
                response["plugin_b"] = True
                return response

        chain = PluginChain()
        chain.add(PluginA())
        chain.add(PluginB())
        await chain.startup_all({})

        result = await chain.enrich({"id": "test"})

        assert execution_order == ["a", "b"]
        assert result["plugin_a"] is True
        assert result["plugin_b"] is True

    @pytest.mark.asyncio
    async def test_empty_chain(self):
        """An empty plugin chain should pass through the response unchanged."""
        chain = PluginChain()

        response = {"id": "org.test", "name": "Test"}
        result = await chain.enrich(response)

        assert result == {"id": "org.test", "name": "Test"}
