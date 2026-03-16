"""Tests for the deep merge algorithm."""

import pytest

from ga4gh_sidecar.merger import merge_service_info


class TestMergeServiceInfo:
    """Test the merge_service_info function with various scenarios."""

    def test_sidecar_wins_for_identity_fields(self):
        """Sidecar config should override backend for id, name, organization, etc."""
        sidecar = {
            "id": "org.institute.tes",
            "name": "Institute TES",
            "organization": {"name": "My Institute", "url": "https://institute.org"},
            "contactUrl": "mailto:ops@institute.org",
        }
        backend = {
            "id": "org.backend.tes",
            "name": "Backend TES",
            "organization": {"name": "Backend Labs", "url": "https://backend.org"},
            "contactUrl": "mailto:backend@backend.org",
        }

        result = merge_service_info(sidecar, backend)

        assert result["id"] == "org.institute.tes"
        assert result["name"] == "Institute TES"
        assert result["organization"]["name"] == "My Institute"
        assert result["contactUrl"] == "mailto:ops@institute.org"

    def test_backend_wins_for_capability_fields(self):
        """Backend should win for storage, workflow_type_versions, etc."""
        sidecar = {
            "id": "org.test",
            "storage": ["s3"],  # sidecar has some default
        }
        backend = {
            "storage": ["s3", "ftp", "gs"],
            "workflow_type_versions": {"CWL": {"versions": ["1.0"]}},
        }

        result = merge_service_info(sidecar, backend)

        assert result["storage"] == ["s3", "ftp", "gs"]
        assert result["workflow_type_versions"] == {"CWL": {"versions": ["1.0"]}}

    def test_arrays_are_concatenated_for_non_authoritative_fields(self):
        """Non-authoritative array fields should be merged and deduplicated."""
        sidecar = {"tags": ["production", "us-east"]}
        backend = {"tags": ["production", "genomics"]}

        result = merge_service_info(sidecar, backend)

        assert set(result["tags"]) == {"production", "us-east", "genomics"}

    def test_nested_dicts_are_recursively_merged(self):
        """Nested dicts (like type, extension) should be recursively merged."""
        sidecar = {
            "type": {"group": "org.ga4gh", "artifact": "tes"},
            "extension": {"sidecar_version": "0.1.0"},
        }
        backend = {
            "type": {"version": "1.1.0"},
            "extension": {"engine": "funnel", "build": "abc123"},
        }

        result = merge_service_info(sidecar, backend)

        assert result["type"]["group"] == "org.ga4gh"
        assert result["type"]["artifact"] == "tes"
        assert result["type"]["version"] == "1.1.0"
        assert result["extension"]["sidecar_version"] == "0.1.0"
        assert result["extension"]["engine"] == "funnel"

    def test_missing_backend_response_uses_sidecar_config(self):
        """When a field only exists in sidecar config, use it."""
        sidecar = {
            "id": "org.test",
            "description": "My TES service",
            "environment": "production",
        }
        backend = {}

        result = merge_service_info(sidecar, backend)

        assert result["id"] == "org.test"
        assert result["description"] == "My TES service"
        assert result["environment"] == "production"

    def test_missing_sidecar_config_uses_backend(self):
        """When a field only exists in backend response, use it."""
        sidecar = {"id": "org.test"}
        backend = {
            "createdAt": "2025-01-01T00:00:00Z",
            "updatedAt": "2025-06-01T00:00:00Z",
        }

        result = merge_service_info(sidecar, backend)

        assert result["id"] == "org.test"
        assert result["createdAt"] == "2025-01-01T00:00:00Z"
        assert result["updatedAt"] == "2025-06-01T00:00:00Z"

    def test_full_realistic_merge(self):
        """Test a realistic merge scenario with sidecar + TES backend."""
        sidecar = {
            "id": "org.demo.tes",
            "name": "GA4GH Demo TES",
            "type": {"group": "org.ga4gh", "artifact": "tes", "version": "1.1.0"},
            "organization": {
                "name": "Demo Institute",
                "url": "https://demo.ga4gh.org",
            },
            "contactUrl": "mailto:ops@demo.ga4gh.org",
            "environment": "production",
            "version": "2.0.0",
        }
        backend = {
            "id": "org.funnel.local",
            "name": "Funnel TES",
            "type": {"group": "org.ga4gh", "artifact": "tes", "version": "1.1.0"},
            "organization": {
                "name": "OHSU",
                "url": "https://ohsu.edu",
            },
            "storage": ["s3", "file", "http"],
            "version": "0.10.0",
            "createdAt": "2024-01-01T00:00:00Z",
        }

        result = merge_service_info(sidecar, backend)

        # Sidecar wins identity
        assert result["id"] == "org.demo.tes"
        assert result["name"] == "GA4GH Demo TES"
        assert result["organization"]["name"] == "Demo Institute"
        assert result["contactUrl"] == "mailto:ops@demo.ga4gh.org"
        assert result["environment"] == "production"

        # Backend wins capabilities
        assert result["storage"] == ["s3", "file", "http"]

        # Backend-only fields pass through
        assert result["createdAt"] == "2024-01-01T00:00:00Z"

        # Type is recursively merged (both have same values here)
        assert result["type"]["artifact"] == "tes"
        assert result["type"]["version"] == "1.1.0"
