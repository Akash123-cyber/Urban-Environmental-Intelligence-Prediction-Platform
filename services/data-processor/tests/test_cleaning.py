from fastapi.testclient import TestClient
from app.main import app
from app.cleaning import calculate_aqi, is_anomaly


def test_calculate_aqi():
    # PM2.5 = 25 -> Good (0-50)
    assert calculate_aqi(25, None) is not None
    assert 0 <= calculate_aqi(25, None) <= 50

    # PM2.5 = 150 -> Unhealthy / Poor (301-400)
    assert calculate_aqi(150, None) is not None
    assert calculate_aqi(150, None) > 300

    # None inputs
    assert calculate_aqi(None, None) is None


def test_is_anomaly():
    assert is_anomaly(600, 100, 100) is True  # extreme PM2.5 spike
    assert is_anomaly(30, 50, 480) is True    # hazardous AQI spike
    assert is_anomaly(35, 60, 90) is False    # nominal readings


def test_processor_health_endpoint():
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"
