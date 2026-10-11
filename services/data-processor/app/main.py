import logging
import time
from datetime import datetime, timezone
from typing import Any

import pandas as pd
from fastapi import FastAPI, HTTPException, Response, Request
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST, Counter, Histogram, Gauge

from .config import settings
from .cleaning import calculate_aqi, is_anomaly
from .s3_archive import archive_raw_batch, archive_processed_parquet
from .repo import (
    get_latest_timestamps,
    ensure_cities,
    upsert_air_batch,
    upsert_weather_batch,
    create_alerts,
    get_engine,
)

logging.basicConfig(level=settings.LOG_LEVEL, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("processor.main")

PROCESSOR_RECORDS_INGESTED_TOTAL = Counter(
    "processor_records_ingested_total",
    "Number of records processed and stored",
    ["data_type", "status"],
)
PROCESSOR_INGEST_DURATION_SECONDS = Histogram(
    "processor_ingest_duration_seconds",
    "Processing time for batch ingestion",
)
PROCESSOR_LAST_INGEST_TIMESTAMP_SECONDS = Gauge(
    "processor_last_ingest_timestamp_seconds",
    "Epoch timestamp of the most recent successful ingest",
)

app = FastAPI(title="Urban EIPP Data Processor", version="1.0.0")


@app.get("/health")
def health():
    return {"status": "healthy", "service": "data-processor", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.get("/ready")
def ready():
    try:
        with get_engine().connect() as conn:
            conn.execute(pd.io.sql.text("SELECT 1;"))
        return {"status": "ready", "database": "connected"}
    except Exception as exc:
        logger.error("Readiness check failed: %s", exc)
        raise HTTPException(status_code=503, detail="Database not ready")


@app.get("/metrics")
def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/latest")
def get_latest():
    """Returns stored observation freshness keyed by city slug."""
    try:
        freshness_map = get_latest_timestamps()
        return freshness_map
    except Exception as exc:
        logger.error("Failed fetching latest timestamps: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/ingest")
async def ingest_batch(payload: dict[str, Any]):
    """
    Ingests a cycle batch.
    Order of operations:
      1. Normalize & prepare observations
      2. Write S3 Raw JSON
      3. Write S3 Processed Parquet
      4. Commit PostgreSQL upserts
    """
    with PROCESSOR_INGEST_DURATION_SECONDS.time():
        cycle_id = payload.get("cycle_id", f"cycle_{int(time.time())}")
        items = payload.get("items", [])
        if not items:
            return {"status": "ignored", "message": "No items in batch"}

        logger.info("Processing ingest batch: %s (%d cities)", cycle_id, len(items))

        # 1. Normalize items into structured lists
        city_meta_list = []
        raw_air_records = []
        raw_weather_records = []
        parquet_rows = []

        for item in items:
            city = item.get("city")
            if not city or "slug" not in city:
                continue
            city_meta_list.append(city)
            slug = city["slug"]

            # Parse air quality
            air = item.get("air", {}).get("hourly", {})
            air_times = air.get("time", [])
            pm25_vals = air.get("pm2_5", [])
            pm10_vals = air.get("pm10", [])
            no2_vals = air.get("nitrogen_dioxide", [])
            o3_vals = air.get("ozone", [])
            co_vals = air.get("carbon_monoxide", [])
            so2_vals = air.get("sulphur_dioxide", [])

            for idx, t_str in enumerate(air_times):
                try:
                    obs_time = datetime.fromisoformat(t_str.replace("Z", "+00:00"))
                    if obs_time.tzinfo is None:
                        obs_time = obs_time.replace(tzinfo=timezone.utc)
                except Exception:
                    continue

                pm25 = pm25_vals[idx] if idx < len(pm25_vals) else None
                pm10 = pm10_vals[idx] if idx < len(pm10_vals) else None
                no2 = no2_vals[idx] if idx < len(no2_vals) else None
                o3 = o3_vals[idx] if idx < len(o3_vals) else None
                co = co_vals[idx] if idx < len(co_vals) else None
                so2 = so2_vals[idx] if idx < len(so2_vals) else None
                aqi = calculate_aqi(pm25, pm10)
                anomaly = is_anomaly(pm25, pm10, aqi)

                raw_air_records.append({
                    "slug": slug,
                    "observed_at": obs_time,
                    "pm25": pm25,
                    "pm10": pm10,
                    "no2": no2,
                    "o3": o3,
                    "co": co,
                    "so2": so2,
                    "aqi": aqi,
                    "is_anomaly": anomaly,
                    "source": "open-meteo",
                })

            # Parse weather
            weather = item.get("weather", {}).get("hourly", {})
            wx_times = weather.get("time", [])
            temp_vals = weather.get("temperature_2m", [])
            rh_vals = weather.get("relative_humidity_2m", [])
            ws_vals = weather.get("wind_speed_10m", [])

            for idx, t_str in enumerate(wx_times):
                try:
                    obs_time = datetime.fromisoformat(t_str.replace("Z", "+00:00"))
                    if obs_time.tzinfo is None:
                        obs_time = obs_time.replace(tzinfo=timezone.utc)
                except Exception:
                    continue

                temp = temp_vals[idx] if idx < len(temp_vals) else None
                rh = rh_vals[idx] if idx < len(rh_vals) else None
                ws = ws_vals[idx] if idx < len(ws_vals) else None

                raw_weather_records.append({
                    "slug": slug,
                    "observed_at": obs_time,
                    "temperature": temp,
                    "humidity": rh,
                    "wind_speed": ws,
                })

        # Build Parquet DataFrame
        df_air = pd.DataFrame(raw_air_records) if raw_air_records else pd.DataFrame()
        df_wx = pd.DataFrame(raw_weather_records) if raw_weather_records else pd.DataFrame()
        if not df_air.empty and not df_wx.empty:
            df_combined = pd.merge(df_air, df_wx, on=["slug", "observed_at"], how="outer")
        elif not df_air.empty:
            df_combined = df_air
        else:
            df_combined = df_wx

        # 2. Archive Raw S3
        raw_key = None
        try:
            raw_key = archive_raw_batch(cycle_id, payload)
        except Exception as exc:
            PROCESSOR_RECORDS_INGESTED_TOTAL.labels(data_type="raw", status="error").inc()
            logger.error("S3 Raw write failed: %s", exc)
            raise HTTPException(status_code=502, detail=f"S3 raw archive failed: {exc}")

        # 3. Archive Processed S3 Parquet
        processed_key = None
        try:
            if not df_combined.empty:
                processed_key = archive_processed_parquet(cycle_id, df_combined)
        except Exception as exc:
            PROCESSOR_RECORDS_INGESTED_TOTAL.labels(data_type="parquet", status="error").inc()
            logger.error("S3 Processed Parquet write failed: %s", exc)
            raise HTTPException(status_code=502, detail=f"S3 processed archive failed: {exc}")

        # 4. Upsert into PostgreSQL
        try:
            slug_to_id = ensure_cities(city_meta_list)

            # Map slug to city_id
            air_to_insert = []
            alerts_to_insert = []
            for r in raw_air_records:
                cid = slug_to_id.get(r["slug"])
                if cid:
                    record_dict = dict(r)
                    del record_dict["slug"]
                    record_dict["city_id"] = cid
                    air_to_insert.append(record_dict)

                    if r["aqi"] and r["aqi"] >= 300:
                        alerts_to_insert.append({
                            "city_id": cid,
                            "type": "high_aqi",
                            "severity": "critical" if r["aqi"] >= 400 else "warning",
                            "message": f"Severe Air Quality Index of {r['aqi']} observed",
                            "created_at": datetime.now(timezone.utc),
                        })
                    elif r["is_anomaly"]:
                        alerts_to_insert.append({
                            "city_id": cid,
                            "type": "anomaly",
                            "severity": "warning",
                            "message": f"Unusual pollutant spike detected in {r.get('slug')}",
                            "created_at": datetime.now(timezone.utc),
                        })

            wx_to_insert = []
            for r in raw_weather_records:
                cid = slug_to_id.get(r["slug"])
                if cid:
                    record_dict = dict(r)
                    del record_dict["slug"]
                    record_dict["city_id"] = cid
                    wx_to_insert.append(record_dict)

            air_count = upsert_air_batch(air_to_insert)
            wx_count = upsert_weather_batch(wx_to_insert)
            alert_count = create_alerts(alerts_to_insert)

            PROCESSOR_RECORDS_INGESTED_TOTAL.labels(data_type="air", status="success").inc(air_count)
            PROCESSOR_RECORDS_INGESTED_TOTAL.labels(data_type="weather", status="success").inc(wx_count)
            PROCESSOR_LAST_INGEST_TIMESTAMP_SECONDS.set(time.time())

            logger.info("Cycle %s successfully stored: %d air rows, %d wx rows, %d alerts", cycle_id, air_count, wx_count, alert_count)
            return {
                "cycle_id": cycle_id,
                "status": "success",
                "raw_s3_key": raw_key,
                "processed_s3_key": processed_key,
                "air_records": air_count,
                "weather_records": wx_count,
                "alerts_created": alert_count,
            }
        except Exception as exc:
            PROCESSOR_RECORDS_INGESTED_TOTAL.labels(data_type="database", status="error").inc()
            logger.error("PostgreSQL upsert failed: %s", exc)
            raise HTTPException(status_code=500, detail=f"Database commit failed: {exc}")
