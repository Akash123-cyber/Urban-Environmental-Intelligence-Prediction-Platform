from fastapi.testclient import TestClient

from app.main import app


def test_train_endpoint_is_forbidden_in_pretrained_mode(monkeypatch):
    import app.main as main
    monkeypatch.setattr(main, "USE_PRETRAINED", True)
    client = TestClient(app)
    response = client.post("/train")
    assert response.status_code == 403
    assert "inference-only" in response.json()["detail"]
