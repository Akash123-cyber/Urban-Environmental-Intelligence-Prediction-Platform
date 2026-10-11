#!/usr/bin/env python3
"""
Archive Replay Script for Disaster Recovery.
Replays archived raw/processed batches from S3 into PostgreSQL.
"""
import io
import json
import logging
import os
import sys
import boto3
import pandas as pd
from sqlalchemy import create_engine, text

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("replay_archive")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://urban:urban_dev_password@localhost:5432/urban")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
S3_ENDPOINT_URL = os.getenv("S3_ENDPOINT_URL", "")
S3_PROCESSED_BUCKET = os.getenv("S3_PROCESSED_BUCKET", "urban-processed")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "")


def get_s3_client():
    kwargs = {"region_name": AWS_REGION}
    if S3_ENDPOINT_URL:
        kwargs["endpoint_url"] = S3_ENDPOINT_URL
    if AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY:
        kwargs["aws_access_key_id"] = AWS_ACCESS_KEY_ID
        kwargs["aws_secret_access_key"] = AWS_SECRET_ACCESS_KEY
    return boto3.client("s3", **kwargs)


def replay_all_processed():
    s3 = get_s3_client()
    engine = create_engine(DATABASE_URL)
    logger.info("Starting archive replay into %s", DATABASE_URL)

    # 1. Fetch cities mapping
    slug_to_id = {}
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT id, slug FROM cities;")).fetchall()
        for r in rows:
            slug_to_id[r.slug] = r.id

    paginator = s3.get_paginator("list_objects_v2")
    replayed_count = 0

    for page in paginator.paginate(Bucket=S3_PROCESSED_BUCKET, Prefix="processed/batches/"):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if not key.endswith(".parquet"):
                continue

            logger.info("Replaying batch: %s", key)
            resp = s3.get_object(Bucket=S3_PROCESSED_BUCKET, Key=key)
            df = pd.read_parquet(io.BytesIO(resp["Body"].read()))

            slug_col = "slug" if "slug" in df.columns else "city_slug"
            with engine.begin() as conn:
                for _, row in df.iterrows():
                    slug = row.get(slug_col)
                    cid = slug_to_id.get(slug)
                    if not cid:
                        continue

                    obs_time = row["observed_at"]
                    # Replay air quality
                    if "pm25" in row and pd.notna(row["pm25"]):
                        conn.execute(text("""
                            INSERT INTO air_quality_data (
                                city_id, observed_at, pm25, pm10, no2, o3, co, so2, aqi, is_anomaly, source
                            )
                            VALUES (
                                :city_id, :observed_at, :pm25, :pm10, :no2, :o3, :co, :so2, :aqi, :is_anomaly, :source
                            )
                            ON CONFLICT (city_id, observed_at) DO UPDATE SET
                                pm25 = COALESCE(EXCLUDED.pm25, air_quality_data.pm25),
                                pm10 = COALESCE(EXCLUDED.pm10, air_quality_data.pm10),
                                aqi  = COALESCE(EXCLUDED.aqi, air_quality_data.aqi);
                        """), {
                            "city_id": cid,
                            "observed_at": obs_time,
                            "pm25": row.get("pm25"),
                            "pm10": row.get("pm10"),
                            "no2": row.get("no2"),
                            "o3": row.get("o3"),
                            "co": row.get("co"),
                            "so2": row.get("so2"),
                            "aqi": row.get("aqi"),
                            "is_anomaly": bool(row.get("is_anomaly", False)),
                            "source": row.get("source", "replay"),
                        })

                    # Replay weather
                    if "temperature" in row and pd.notna(row["temperature"]):
                        conn.execute(text("""
                            INSERT INTO weather_data (city_id, observed_at, temperature, humidity, wind_speed)
                            VALUES (:city_id, :observed_at, :temperature, :humidity, :wind_speed)
                            ON CONFLICT (city_id, observed_at) DO UPDATE SET
                                temperature = COALESCE(EXCLUDED.temperature, weather_data.temperature),
                                humidity    = COALESCE(EXCLUDED.humidity, weather_data.humidity),
                                wind_speed  = COALESCE(EXCLUDED.wind_speed, weather_data.wind_speed);
                        """), {
                            "city_id": cid,
                            "observed_at": obs_time,
                            "temperature": row.get("temperature"),
                            "humidity": row.get("humidity"),
                            "wind_speed": row.get("wind_speed"),
                        })
                    replayed_count += 1

    logger.info("Archive replay complete. Replayed %d records.", replayed_count)


if __name__ == "__main__":
    replay_all_processed()
