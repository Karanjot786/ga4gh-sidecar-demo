"""Integration tests — spin up sidecar + mock backend in-process."""

from fastapi.testclient import TestClient

from mock_backend.app import app as mock_app


class TestMockBackend:
    """Test that the mock TES backend works correctly on its own."""

    def test_service_info(self):
        """Mock should return a valid /service-info response."""
        client = TestClient(mock_app)
        resp = client.get("/service-info")
        assert resp.status_code == 200

        data = resp.json()
        assert data["id"] == "org.mock.tes-backend"
        assert data["type"]["artifact"] == "tes"
        assert "storage" in data
        assert "s3" in data["storage"]

    def test_create_task(self):
        """Mock should accept POST /tasks and return a task ID."""
        client = TestClient(mock_app)
        resp = client.post("/tasks", json={"name": "test-alignment"})
        assert resp.status_code == 200

        data = resp.json()
        assert "id" in data

    def test_get_task(self):
        """Mock should return task status for a created task."""
        client = TestClient(mock_app)
        create_resp = client.post("/tasks", json={"name": "test-task"})
        task_id = create_resp.json()["id"]

        get_resp = client.get(f"/tasks/{task_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["state"] == "QUEUED"

    def test_get_nonexistent_task(self):
        """Mock should return 404 for unknown task IDs."""
        client = TestClient(mock_app)
        resp = client.get("/tasks/nonexistent-id")
        assert resp.status_code == 404

    def test_list_tasks(self):
        """Mock should list all tasks."""
        client = TestClient(mock_app)
        resp = client.get("/tasks")
        assert resp.status_code == 200
        assert "tasks" in resp.json()
