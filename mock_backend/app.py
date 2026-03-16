"""Mock GA4GH TES backend for testing the sidecar.

Simulates a TES server that:
- Returns a /service-info response with TES-specific fields
- Accepts POST /tasks to create a mock task  
- Returns GET /tasks/{id} with a mock task status

This backend is only for demo and testing purposes.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI(
    title="Mock GA4GH TES Backend",
    description="A mock TES server for testing the ServiceInfo Sidecar.",
    version="0.1.0",
)

# In-memory task store
_tasks: dict[str, dict[str, Any]] = {}


@app.get("/service-info")
async def service_info() -> dict[str, Any]:
    """Return TES-style /service-info.

    This simulates what a real TES backend like Funnel would return.
    The sidecar will merge this with its own configuration.
    """
    return {
        "id": "org.mock.tes-backend",
        "name": "Mock TES Backend",
        "type": {
            "group": "org.ga4gh",
            "artifact": "tes",
            "version": "1.1.0",
        },
        "description": "A mock Task Execution Service for testing.",
        "organization": {
            "name": "Mock Labs",
            "url": "https://mock-labs.example.org",
        },
        "contactUrl": "mailto:nobody@mock-labs.example.org",
        "version": "0.1.0",
        "environment": "development",
        "storage": ["s3", "ftp", "file"],
        "createdAt": "2025-01-01T00:00:00Z",
        "updatedAt": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/tasks")
async def create_task(task: dict[str, Any] | None = None) -> dict[str, str]:
    """Create a mock TES task.

    Demonstrates that non-/service-info requests are properly
    forwarded through the sidecar.
    """
    task_id = str(uuid.uuid4())
    _tasks[task_id] = {
        "id": task_id,
        "state": "QUEUED",
        "name": (task or {}).get("name", "unnamed-task"),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    return {"id": task_id}


@app.get("/tasks/{task_id}")
async def get_task(task_id: str) -> dict[str, Any]:
    """Get a mock task status."""
    if task_id in _tasks:
        return _tasks[task_id]
    return JSONResponse(
        status_code=404,
        content={"error": f"Task {task_id} not found"},
    )


@app.get("/tasks")
async def list_tasks() -> dict[str, Any]:
    """List all mock tasks."""
    return {"tasks": list(_tasks.values())}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9090)
