"""Tests for the configuration loading."""

from pathlib import Path

import yaml

from ga4gh_sidecar.config import SidecarConfig


class TestSidecarConfig:
    """Test configuration loading and validation."""

    def _write_config(self, data: dict, tmp_path: Path) -> Path:
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump(data))
        return config_file

    def test_loads_valid_config(self, tmp_path):
        """Should load a valid YAML config without errors."""
        data = {
            "listen_port": 8080,
            "backend_url": "http://localhost:9090",
            "service_info": {
                "id": "org.test.tes",
                "name": "Test TES",
                "type": {
                    "group": "org.ga4gh",
                    "artifact": "tes",
                    "version": "1.1.0",
                },
                "organization": {
                    "name": "Test Org",
                    "url": "https://test.org",
                },
            },
        }
        config_file = self._write_config(data, tmp_path)
        config = SidecarConfig.from_yaml(config_file)

        assert config.listen_port == 8080
        assert config.backend_url == "http://localhost:9090"
        assert config.service_info.id == "org.test.tes"
        assert config.service_info.type.artifact == "tes"
        assert config.service_info.organization.name == "Test Org"

    def test_defaults_are_applied(self, tmp_path):
        """Missing optional fields should use defaults."""
        data = {
            "service_info": {
                "id": "org.test",
                "name": "Test",
                "type": {"artifact": "tes", "version": "1.0.0"},
                "organization": {"name": "Org", "url": "https://org.dev"},
            },
        }
        config_file = self._write_config(data, tmp_path)
        config = SidecarConfig.from_yaml(config_file)

        assert config.listen_port == 8080
        assert config.backend_url == "http://localhost:9090"
        assert config.merge.poll_interval_seconds == 30
        assert config.merge.fallback == "serve_config_only"
        assert config.security.rate_limit_rps == 100
        assert config.plugins == []

    def test_service_info_to_dict(self, tmp_path):
        """ServiceInfoConfig.to_dict() should produce a clean JSON-ready dict."""
        data = {
            "service_info": {
                "id": "org.test",
                "name": "Test",
                "type": {"artifact": "tes", "version": "1.0.0"},
                "organization": {"name": "Org", "url": "https://org.dev"},
                "environment": "staging",
            },
        }
        config_file = self._write_config(data, tmp_path)
        config = SidecarConfig.from_yaml(config_file)

        d = config.service_info.to_dict()
        assert d["id"] == "org.test"
        assert d["type"]["artifact"] == "tes"
        assert d["environment"] == "staging"
        assert isinstance(d, dict)

    def test_plugins_config(self, tmp_path):
        """Should parse plugin entries with configs."""
        data = {
            "service_info": {
                "id": "org.test",
                "name": "Test",
                "type": {"artifact": "tes", "version": "1.0.0"},
                "organization": {"name": "Org", "url": "https://org.dev"},
            },
            "plugins": [
                {"name": "tes", "config": {"override_protocols": ["s3"]}},
                {"name": "wes", "config": {}},
            ],
        }
        config_file = self._write_config(data, tmp_path)
        config = SidecarConfig.from_yaml(config_file)

        assert len(config.plugins) == 2
        assert config.plugins[0].name == "tes"
        assert config.plugins[0].config["override_protocols"] == ["s3"]
        assert config.plugins[1].name == "wes"
