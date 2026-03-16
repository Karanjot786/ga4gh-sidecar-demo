# GA4GH ServiceInfo Sidecar

A reverse proxy sidecar for GA4GH services that intercepts `/service-info` requests, dynamically merges metadata from operator config and backend services, and forwards all other traffic unchanged.

<!-- **This is a demo prototype built as part of a [GSoC 2026 proposal](https://summerofcode.withgoogle.com/) for the [Global Alliance for Genomics and Health (GA4GH)](https://www.ga4gh.org/).** -->

## What It Does

```
Client → Sidecar (port 8080) → Backend GA4GH Service (port 9090)
                |
                ├── GET /service-info  → Returns merged response (sidecar config + backend)
                ├── GET /health        → Returns health status
                └── Everything else    → Forwarded to backend unchanged
```

The sidecar solves a real problem: every GA4GH implementation (Funnel, Cromwell, TESK, Dockstore) handles `/service-info` inside its own codebase. When you deploy three services, you get three inconsistent responses and three places to update metadata. The sidecar centralizes this.

## Quick Start

### Option 1: Run locally (no Docker)

```bash
# Install the package
pip install -e ".[dev]"

# Start the mock TES backend
uvicorn mock_backend.app:app --port 9090 &

# Start the sidecar
uvicorn ga4gh_sidecar.main:app --port 8080

# In another terminal:
curl http://localhost:8080/service-info | python -m json.tool
curl -X POST http://localhost:8080/tasks -H "Content-Type: application/json" -d '{"name": "test"}'
curl http://localhost:8080/health
```

### Option 2: Docker Compose

```bash
docker compose up --build

# Test it:
curl http://localhost:8080/service-info | python -m json.tool
```

## How the Merge Works

The sidecar polls the backend's `/service-info` every 15 seconds and merges it with the operator's config:

| Field | Who Wins | Why |
|-------|----------|-----|
| `id`, `name`, `organization` | **Sidecar config** | Operator controls identity |
| `contactUrl`, `environment` | **Sidecar config** | Operator controls ops metadata |
| `storage`, `workflow_type_versions` | **Backend** | Backend knows its capabilities |
| `extension` (nested) | **Recursively merged** | Both can contribute |
| `createdAt`, `updatedAt` | **Backend** | Backend tracks its own lifecycle |

## Plugin System

Plugins enrich the `/service-info` response with service-specific metadata:

```python
from ga4gh_sidecar.plugins.base import SidecarPlugin

class MyPlugin(SidecarPlugin):
    def name(self) -> str:
        return "my-plugin"

    async def enrich_service_info(self, response: dict) -> dict:
        response.setdefault("extension", {})["custom_field"] = "value"
        return response
```

Built-in plugins:
- **TES** — injects `storage` protocols
- **WES** — injects `workflow_type_versions`

## Configuration

See [`config.yaml`](config.yaml) for the full config schema. Key fields:

```yaml
service_info:
  id: "org.your-institute.tes"
  name: "Your TES"
  type:
    group: "org.ga4gh"
    artifact: "tes"
    version: "1.1.0"
  organization:
    name: "Your Institute"
    url: "https://your-institute.org"

plugins:
  - name: "tes"
    config:
      override_protocols: ["s3", "gs"]
```

## Tests

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

## Project Structure

```
├── src/ga4gh_sidecar/
│   ├── main.py          # FastAPI app, routes, lifespan
│   ├── config.py        # Pydantic config models
│   ├── proxy.py         # httpx reverse proxy
│   ├── merger.py        # Deep merge algorithm + cache
│   └── plugins/
│       ├── base.py      # Plugin ABC + chain
│       ├── tes.py       # TES storage plugin
│       └── wes.py       # WES workflow plugin
├── mock_backend/
│   └── app.py           # Mock TES backend
├── tests/               # pytest test suite
├── config.yaml          # Example configuration
├── Dockerfile           # Multi-stage, non-root
├── docker-compose.yml   # Sidecar + mock backend
└── pyproject.toml       # Package config
```

## License

Apache 2.0
