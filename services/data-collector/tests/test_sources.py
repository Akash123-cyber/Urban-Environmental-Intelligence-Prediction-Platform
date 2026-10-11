from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from app.main import app
from app.sources import plan_cycle


def test_plan_cycle_fresh_cities():
    cities = [
        {"slug": "delhi", "name": "Delhi"},
        {"slug": "mumbai", "name": "Mumbai"},
    ]
    now = datetime(2026, 10, 11, 14, 0, tzinfo=timezone.utc)
    latest_timestamps = {
        "delhi": {
            "air_latest": "2026-10-11T13:00:00Z",
            "weather_latest": "2026-10-11T13:00:00Z",
        },
        "mumbai": {
            "air_latest": "2026-10-11T13:00:00Z",
            "weather_latest": "2026-10-11T13:00:00Z",
        },
    }
    due = plan_cycle(cities, latest_timestamps, live_lookback_hours=2, now=now)
    assert due == [], "Fresh cities must result in zero due cities"


def test_plan_cycle_due_cities():
    cities = [
        {"slug": "delhi", "name": "Delhi"},
        {"slug": "mumbai", "name": "Mumbai"},
    ]
    now = datetime(2026, 10, 11, 14, 0, tzinfo=timezone.utc)
    latest_timestamps = {
        "delhi": {
            "air_latest": "2026-10-11T10:00:00Z",  # 4 hours old
            "weather_latest": "2026-10-11T10:00:00Z",
        },
        "mumbai": {
            "air_latest": "2026-10-11T13:00:00Z",
            "weather_latest": "2026-10-11T13:00:00Z",
        },
    }
    due = plan_cycle(cities, latest_timestamps, live_lookback_hours=2, now=now)
    assert len(due) == 1
    assert due[0]["slug"] == "delhi"


def test_collector_health_endpoint():
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"
