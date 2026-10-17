import os
from pathlib import Path

os.environ["APIFORGE_TESTING"] = "1"
os.environ["APIFORGE_DATABASE_URL"] = "sqlite:///./test_apiforge.db"

from fastapi.testclient import TestClient

from app.database import Base, engine
from app.main import app


def setup_module() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


client = TestClient(app)


def test_sample_endpoint_and_docs() -> None:
    response = client.get("/api/sample/hello")
    assert response.status_code == 200
    assert response.json()["service"] == "sample"
    assert client.get("/docs").status_code == 200


def test_request_crud() -> None:
    created = client.post("/api/requests", json={"name": "Sample", "method": "GET", "url": "https://example.com", "headers": {}, "query_params": {}, "monitor_enabled": True})
    assert created.status_code == 201
    request_id = created.json()["id"]
    updated = client.put(f"/api/requests/{request_id}", json={"name": "Updated", "method": "POST", "url": "https://example.com/api", "headers": {"X-Test": "yes"}, "query_params": {}, "body":{"ok": True}, "monitor_enabled": False})
    assert updated.status_code == 200
    assert updated.json()["method"] == "POST"
    assert client.delete(f"/api/requests/{request_id}").status_code == 204


def test_url_validation_blocks_local_destinations() -> None:
    response = client.post("/api/requests", json={"name": "Unsafe", "method": "GET", "url": "http://localhost:8000/admin"})
    assert response.status_code == 422
    response = client.post("/api/requests", json={"name": "Unsafe", "method": "GET", "url": "http://127.0.0.1:8000/admin"})
    assert response.status_code == 201


def test_validation_for_method_and_url() -> None:
    response = client.post("/api/requests", json={"name": "Bad", "method": "PATCH", "url": "ftp://example.com"})
    assert response.status_code == 422


def test_health_and_metrics_contract() -> None:
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/metrics/latency").json() == []
