"""Configuration models for the GA4GH ServiceInfo Sidecar."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, HttpUrl


class ServiceType(BaseModel):
    """GA4GH ServiceType object — identifies which API this service implements."""

    group: str = Field(
        default="org.ga4gh",
        description="Namespace. 'org.ga4gh' for official GA4GH APIs.",
    )
    artifact: str = Field(
        description="API name: tes, wes, trs, drs, beacon, etc.",
    )
    version: str = Field(
        description="Spec version, e.g. '1.1.0'.",
    )


class Organization(BaseModel):
    """Organization operating this service."""

    name: str
    url: str


class ServiceInfoConfig(BaseModel):
    """Static /service-info fields configured by the operator."""

    id: str = Field(description="Reverse domain name, globally unique.")
    name: str
    type: ServiceType
    organization: Organization
    description: str = ""
    contactUrl: str = ""
    documentationUrl: str = ""
    environment: str = "production"
    version: str = "1.0.0"

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json", exclude_none=True)


class MergeConfig(BaseModel):
    """Controls how sidecar config merges with backend /service-info."""

    poll_interval_seconds: int = Field(default=30, ge=5)
    backend_timeout_seconds: int = Field(default=5, ge=1)
    fallback: str = Field(
        default="serve_config_only",
        description="What to do if backend is unreachable: 'serve_config_only' or 'return_503'",
    )


class SecurityConfig(BaseModel):
    """Security settings."""

    rate_limit_rps: int = Field(default=100, description="Requests per second limit.")
    rate_limit_burst: int = Field(default=200)
    cors_allowed_origins: list[str] = Field(default=["*"])


class PluginEntry(BaseModel):
    """A single plugin with optional config."""

    name: str
    config: dict[str, Any] = Field(default_factory=dict)


class SidecarConfig(BaseModel):
    """Root configuration for the sidecar."""

    listen_port: int = Field(default=8080)
    backend_url: str = Field(default="http://localhost:9090")
    service_info: ServiceInfoConfig
    merge: MergeConfig = Field(default_factory=MergeConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    plugins: list[PluginEntry] = Field(default_factory=list)

    @classmethod
    def from_yaml(cls, path: str | Path) -> SidecarConfig:
        """Load config from a YAML file."""
        with open(path) as f:
            raw = yaml.safe_load(f)
        return cls(**raw)
