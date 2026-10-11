import logging
from datetime import datetime, timezone, timedelta
from typing import Any
import httpx
from prometheus_client import Counter, Histogram, Gauge

logger = logging.getLogger("collector.sources")

COLLECTOR_FETCH_TOTAL = Counter(
    "collector_fetch_total",
    "Upstream API fetch requests count",
    ["source", "status"],
)
COLLECTOR_CYCLE_DURATION_SECONDS = Histogram(
    "collector_cycle_duration_seconds",
    "Time spent in collector poll cycle",
)
COLLECTOR_DUE_CITIES_COUNT = Gauge(
    "collector_due_cities_count",
    "Number of cities due for data refresh in the last cycle",
)


def plan_cycle(
    cities: list[dict],
    latest_timestamps: dict[str, dict[str, Any]],
    live_lookback_hours: int = 2,
    now: datetime = None,
) -> list[dict]:
    """
    Evaluates each city against the processor's stored freshness.
    Returns only cities that need fresh observation data.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    # Upper boundary: previous completed UTC hour
    latest_expected = now.replace(minute=0, second=0, microsecond=0)
    due_cities = []

    for city in cities:
        slug = city["slug"]
        city_freshness = latest_timestamps.get(slug, {})
        air_latest_str = city_freshness.get("air_latest")
        wx_latest_str = city_freshness.get("weather_latest")

        needs_fetch = False
        if not air_latest_str or not wx_latest_str:
            needs_fetch = True
        else:
            try:
                air_latest = datetime.fromisoformat(air_latest_str.replace("Z", "+00:00"))
                wx_latest = datetime.fromisoformat(wx_latest_str.replace("Z", "+00:00"))
                # If latest observation is older than 1 hour ago, fetch
                if air_latest < latest_expected - timedelta(hours=1) or wx_latest < latest_expected - timedelta(hours=1):
                    needs_fetch = True
            except Exception:
                needs_fetch = True

        if needs_fetch:
            due_cities.append(city)

    COLLECTOR_DUE_CITIES_COUNT.set(len(due_cities))
    return due_cities


async def fetch_open_meteo_air(
    client: httpx.AsyncClient,
    lat: float,
    lon: float,
    lookback_hours: int = 2,
) -> dict:
    url = "https://air-quality-api.open-meteo.com/v1/air-quality"
    # past_hours requested for recovery window
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "pm2_5,pm10,nitrogen_dioxide,ozone,carbon_monoxide,sulphur_dioxide,european_aqi",
        "past_hours": lookback_hours,
        "forecast_hours": 1,
    }
    try:
        resp = await client.get(url, params=params, timeout=15.0)
        resp.raise_for_status()
        COLLECTOR_FETCH_TOTAL.labels(source="open-meteo-air", status="success").inc()
        return resp.json()
    except Exception as exc:
        COLLECTOR_FETCH_TOTAL.labels(source="open-meteo-air", status="error").inc()
        logger.error("Failed fetching air quality from open-meteo (lat=%f, lon=%f): %s", lat, lon, exc)
        return {}


async def fetch_open_meteo_weather(
    client: httpx.AsyncClient,
    lat: float,
    lon: float,
    lookback_hours: int = 2,
) -> dict:
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "temperature_2m,relative_humidity_2m,wind_speed_10m",
        "past_hours": lookback_hours,
        "forecast_hours": 1,
    }
    try:
        resp = await client.get(url, params=params, timeout=15.0)
        resp.raise_for_status()
        COLLECTOR_FETCH_TOTAL.labels(source="open-meteo-weather", status="success").inc()
        return resp.json()
    except Exception as exc:
        COLLECTOR_FETCH_TOTAL.labels(source="open-meteo-weather", status="error").inc()
        logger.error("Failed fetching weather from open-meteo (lat=%f, lon=%f): %s", lat, lon, exc)
        return {}
