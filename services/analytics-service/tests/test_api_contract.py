from fastapi.testclient import TestClient

from app.main import app


def test_train_endpoint_is_forbidden_in_pretrained_mode(monkeypatch):
    import app.main as main
    monkeypatch.setattr(main, "USE_PRETRAINED", True)
    client = TestClient(app)
    response = client.post("/train")
    assert response.status_code == 403
    assert "inference-only" in response.json()["detail"]


def test_models_endpoints(monkeypatch):
    import app.main as main
    monkeypatch.setattr(main.registry, "bucket", "mock-model-bucket")
    client = TestClient(app)

    # 1. Test GET /models
    resp = client.get("/models")
    assert resp.status_code == 200
    data = resp.json()
    assert data["mode"] == "pretrained"
    assert "active_version" in data
    assert data["training_enabled"] is False

    # 2. Test GET /models/version
    resp = client.get("/models/version")
    assert resp.status_code == 200
    ver_data = resp.json()
    assert "active_version" in ver_data
    assert "version_source" in ver_data

    # 3. Test POST /models/reload
    resp = client.post("/models/reload")
    assert resp.status_code == 200
    reload_data = resp.json()
    assert reload_data["status"] == "success"
    assert "reload" in reload_data

