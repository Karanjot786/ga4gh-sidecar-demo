# ga4gh-sidecar

A reverse proxy that sits in front of any GA4GH service, takes over the `/service-info` endpoint, and leaves everything else alone.

```
Client → Sidecar (port 8080) → Backend (port 9090)
              |
              ├── GET /service-info  → merged response from config + backend
              ├── GET /health        → health status
              └── anything else      → forwarded to backend as-is
```

## Why this exists

Every GA4GH implementation handles `/service-info` differently. Funnel returns one shape, Cromwell another, TESK another. If you run three services, you get three inconsistent responses and three config files to keep in sync.

The sidecar pulls that logic out. You configure identity fields (who you are, how to reach you) in one YAML file, and the sidecar merges them with whatever the backend reports about its own capabilities. One place to update, consistent responses everywhere.

## Get it running

### Locally (no Docker)

```bash
pip install -e ".[dev]"

# start the mock TES backend
uvicorn mock_backend.app:app --port 9090 &

# start the sidecar
uvicorn ga4gh_sidecar.main:app --port 8080

# try it
curl http://localhost:8080/service-info | python -m json.tool
curl -X POST http://localhost:8080/tasks -H "Content-Type: application/json" -d '{"name": "test"}'
curl http://localhost:8080/health
```

### With Docker Compose

```bash
docker compose up --build

curl http://localhost:8080/service-info | python -m json.tool
```

## How the merge works

The sidecar polls the backend's `/service-info` every 15 seconds and combines it with your config. The precedence rules are explicit:

| Field | Winner | Reason |
|-------|--------|--------|
| `id`, `name`, `organization` | Your config | You control who you are |
| `contactUrl`, `environment` | Your config | Ops metadata is yours |
| `storage`, `workflow_type_versions` | Backend | It knows what it supports |
| `extension` (nested objects) | Both, recursively merged | Either side can add fields |
| `createdAt`, `updatedAt` | Backend | It tracks its own lifecycle |

The rules are two sets of field names in `merger.py`. Takes about 30 seconds to read.

## Merge modes

The sidecar supports two modes: `merge` (default) and `override`.

- `merge`: combines backend and config responses using the precedence rules above
- `override`: ignores the backend's `/service-info` entirely, returns config as the complete response

Set it in config:

```yaml
merge:
  mode: "merge"  # or "override"
```

Override mode covers deployments where the backend's `/service-info` is broken, stale, or nonexistent.

## Plugins

Plugins run after the merge and can add or change fields in the response. Writing one looks like this:

```python
from ga4gh_sidecar.plugins.base import SidecarPlugin

class MyPlugin(SidecarPlugin):
    def name(self) -> str:
        return "my-plugin"

    async def enrich_service_info(self, response: dict) -> dict:
        response.setdefault("extension", {})["custom_field"] = "value"
        return response
```

Ships with two plugins:
- **tes** — adds `storage` protocols (s3, gs, file, etc.)
- **wes** — adds `workflow_type_versions` (CWL, WDL)

Register your own via Python entry points in `pyproject.toml`.

## Configuration

See `config.yaml` for a full example. The minimum you need:

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

25 tests, under a second. Config loading, merge precedence, plugin ordering, mock backend integration.

## Performance

Benchmarks run on MacBook Pro, localhost, `hey` 1000 requests 10 concurrent.

| Path | p50 | p95 | p99 | RPS |
|------|-----|-----|-----|-----|
| `GET /service-info` (cached) | 0.9ms | 3.9ms | 41.6ms | 5348 |
| `GET /tasks` (forwarded) | 10.3ms | 27.3ms | 64.0ms | 749 |

All 2000 requests returned 200.

The `/service-info` path serves a cached in-memory response with no backend call. The `/tasks` numbers include the mock backend's own response time. Sidecar proxy overhead on forwarded paths is the difference between these two baselines. Expect lower absolute latency on server hardware with a real backend over a local network.

## Layout

```
├── src/ga4gh_sidecar/
│   ├── main.py          # FastAPI app, routes, lifespan
│   ├── config.py        # Pydantic config models
│   ├── proxy.py         # httpx reverse proxy
│   ├── merger.py        # merge algorithm + background cache
│   └── plugins/
│       ├── base.py      # plugin ABC + chain
│       ├── tes.py       # TES storage plugin
│       └── wes.py       # WES workflow plugin
├── mock_backend/
│   └── app.py           # mock TES for testing
├── tests/               # pytest suite
├── config.yaml          # example config
├── Dockerfile           # multi-stage, non-root
├── docker-compose.yml   # sidecar + mock backend
└── pyproject.toml
```

## License

Apache 2.0
