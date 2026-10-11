"""PostgreSQL repository for the analytics service."""
from __future__ import annotations

import os
import pandas as pd
from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv("DATABASE_URL", "")
engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_size=3, max_overflow=2) if DATABASE_URL else None


def require_engine():
    if engine is None:
        raise RuntimeError("DATABASE_URL is not configured")
    return engine


def list_cities() -> list[dict]:
    with require_engine().connect() as conn:
        rows = conn.execute(text("SELECT id, slug, name FROM cities ORDER BY state, name"))
        return [dict(r._mapping) for r in rows]


def load_series(city_id: int, hours: int = 24 * 30) -> pd.DataFrame:
    query = text("""
        SELECT a.observed_at, a.pm25, a.pm10, a.no2,
               w.temperature, w.humidity, w.wind_speed
        FROM air_quality_data AS a
        LEFT JOIN weather_data AS w
          ON w.city_id = a.city_id AND w.observed_at = a.observed_at
        WHERE a.city_id = :city_id
          AND a.observed_at >= now() - make_interval(hours => :hours)
        ORDER BY a.observed_at
    """)
    with require_engine().connect() as conn:
        return pd.read_sql(query, conn, params={"city_id": city_id, "hours": hours}, parse_dates=["observed_at"])


def save_predictions(city_id: int, based_on, rows: list[dict]) -> None:
    if not rows:
        return
    payload = [{**row, "city_id": city_id, "based_on": based_on} for row in rows]
    query = text("""
        INSERT INTO predictions
          (city_id, target_time, predicted_pm25, predicted_pm10, model_version, generated_at, based_on)
        VALUES
          (:city_id, :target_time, :predicted_pm25, :predicted_pm10, :model_version, now(), :based_on)
        ON CONFLICT (city_id, target_time) DO UPDATE SET
          predicted_pm25 = EXCLUDED.predicted_pm25,
          predicted_pm10 = EXCLUDED.predicted_pm10,
          model_version = EXCLUDED.model_version,
          generated_at = now(),
          based_on = EXCLUDED.based_on
        WHERE predictions.based_on IS NULL OR predictions.based_on < EXCLUDED.based_on
    """)
    with require_engine().begin() as conn:
        conn.execute(query, payload)


def latest_measurement_time(city_id: int):
    query = text("SELECT max(observed_at) FROM air_quality_data WHERE city_id = :city_id")
    with require_engine().connect() as conn:
        return conn.execute(query, {"city_id": city_id}).scalar()


def latest_prediction_based_on(city_id: int):
    query = text("SELECT max(based_on) FROM predictions WHERE city_id = :city_id")
    with require_engine().connect() as conn:
        return conn.execute(query, {"city_id": city_id}).scalar()


def get_predictions(city_id: int, limit: int = 72) -> list[dict]:
    query = text("""
        SELECT target_time, predicted_pm25, predicted_pm10, model_version, generated_at, based_on
        FROM predictions
        WHERE city_id = :city_id AND target_time > now()
        ORDER BY target_time
        LIMIT :limit
    """)
    with require_engine().connect() as conn:
        rows = conn.execute(query, {"city_id": city_id, "limit": limit})
        return [dict(row._mapping) for row in rows]
