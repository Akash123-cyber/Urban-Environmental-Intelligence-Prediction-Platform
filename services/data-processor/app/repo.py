import logging
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from .config import settings

logger = logging.getLogger("processor.repo")

_engine: Optional[Engine] = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True, pool_size=5, max_overflow=10)
    return _engine


def get_latest_timestamps() -> dict[str, dict[str, Optional[str]]]:
    """Queries newest observed_at for each city from air_quality_data and weather_data."""
    engine = get_engine()
    out = {}

    query = text("""
        SELECT 
            c.slug,
            to_char(MAX(a.observed_at) AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"') AS air_latest,
            to_char(MAX(w.observed_at) AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"') AS weather_latest
        FROM cities c
        LEFT JOIN air_quality_data a ON c.id = a.city_id
        LEFT JOIN weather_data w ON c.id = w.city_id
        GROUP BY c.slug;
    """)

    with engine.connect() as conn:
        rows = conn.execute(query).fetchall()
        for row in rows:
            out[row.slug] = {
                "air_latest": row.air_latest,
                "weather_latest": row.weather_latest,
            }
    return out


def ensure_cities(city_list: list[dict]) -> dict[str, int]:
    """Upserts cities by slug and returns a map of slug -> city_id."""
    engine = get_engine()
    slug_to_id = {}

    upsert_sql = text("""
        INSERT INTO cities (slug, name, state, country, latitude, longitude)
        VALUES (:slug, :name, :state, :country, :latitude, :longitude)
        ON CONFLICT (slug) DO UPDATE SET
            name = EXCLUDED.name,
            state = EXCLUDED.state,
            latitude = EXCLUDED.latitude,
            longitude = EXCLUDED.longitude
        RETURNING slug, id;
    """)

    with engine.begin() as conn:
        for c in city_list:
            res = conn.execute(upsert_sql, {
                "slug": c["slug"],
                "name": c["name"],
                "state": c.get("state", ""),
                "country": c.get("country", "India"),
                "latitude": c["latitude"],
                "longitude": c["longitude"],
            }).fetchone()
            if res:
                slug_to_id[res.slug] = res.id

    return slug_to_id


def upsert_air_batch(records: list[dict]) -> int:
    """Idempotently upserts air quality observations with COALESCE."""
    if not records:
        return 0
    engine = get_engine()

    sql = text("""
        INSERT INTO air_quality_data (
            city_id, observed_at, pm25, pm10, no2, o3, co, so2, aqi, is_anomaly, source
        )
        VALUES (
            :city_id, :observed_at, :pm25, :pm10, :no2, :o3, :co, :so2, :aqi, :is_anomaly, :source
        )
        ON CONFLICT (city_id, observed_at) DO UPDATE SET
            pm25 = COALESCE(EXCLUDED.pm25, air_quality_data.pm25),
            pm10 = COALESCE(EXCLUDED.pm10, air_quality_data.pm10),
            no2  = COALESCE(EXCLUDED.no2, air_quality_data.no2),
            o3   = COALESCE(EXCLUDED.o3, air_quality_data.o3),
            co   = COALESCE(EXCLUDED.co, air_quality_data.co),
            so2  = COALESCE(EXCLUDED.so2, air_quality_data.so2),
            aqi  = COALESCE(EXCLUDED.aqi, air_quality_data.aqi),
            is_anomaly = EXCLUDED.is_anomaly,
            source = EXCLUDED.source;
    """)

    with engine.begin() as conn:
        conn.execute(sql, records)
    return len(records)


def upsert_weather_batch(records: list[dict]) -> int:
    """Idempotently upserts weather observations with COALESCE."""
    if not records:
        return 0
    engine = get_engine()

    sql = text("""
        INSERT INTO weather_data (city_id, observed_at, temperature, humidity, wind_speed)
        VALUES (:city_id, :observed_at, :temperature, :humidity, :wind_speed)
        ON CONFLICT (city_id, observed_at) DO UPDATE SET
            temperature = COALESCE(EXCLUDED.temperature, weather_data.temperature),
            humidity    = COALESCE(EXCLUDED.humidity, weather_data.humidity),
            wind_speed  = COALESCE(EXCLUDED.wind_speed, weather_data.wind_speed);
    """)

    with engine.begin() as conn:
        conn.execute(sql, records)
    return len(records)


def create_alerts(alerts_list: list[dict]) -> int:
    if not alerts_list:
        return 0
    engine = get_engine()
    sql = text("""
        INSERT INTO alerts (city_id, type, severity, message, created_at)
        VALUES (:city_id, :type, :severity, :message, :created_at);
    """)
    with engine.begin() as conn:
        conn.execute(sql, alerts_list)
    return len(alerts_list)
