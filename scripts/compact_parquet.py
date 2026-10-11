#!/usr/bin/env python3
"""
Nightly Compaction Job for the Urban Environmental Intelligence Platform.
Reads raw cycle batch Parquet files from S3 and rewrites them into
optimized monthly city-partitioned Parquet files:
  processed/city=<slug>/year=YYYY/month=MM/data.parquet
"""
import io
import logging
import os
import sys
from datetime import datetime, timezone
import boto3
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("compact_parquet")

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


def compact_batches(target_date: datetime = None):
    if target_date is None:
        target_date = datetime.now(timezone.utc)

    s3 = get_s3_client()
    prefix = f"processed/batches/{target_date:%Y/%m/}"
    logger.info("Scanning for batch objects with prefix s3://%s/%s", S3_PROCESSED_BUCKET, prefix)

    paginator = s3.get_paginator("list_objects_v2")
    batch_keys = []
    for page in paginator.paginate(Bucket=S3_PROCESSED_BUCKET, Prefix=prefix):
        for obj in page.get("Contents", []):
            if obj["Key"].endswith(".parquet"):
                batch_keys.append(obj["Key"])

    if not batch_keys:
        logger.info("No batch objects found to compact.")
        return

    logger.info("Found %d batch objects. Reading data...", len(batch_keys))
    frames = []
    for k in batch_keys:
        try:
            resp = s3.get_object(Bucket=S3_PROCESSED_BUCKET, Key=k)
            df = pd.read_parquet(io.BytesIO(resp["Body"].read()))
            frames.append(df)
        except Exception as exc:
            logger.error("Failed reading %s: %s", k, exc)

    if not frames:
        logger.warning("No data loaded from batches.")
        return

    combined = pd.concat(frames, ignore_index=True)
    if "observed_at" in combined.columns:
        combined["observed_at"] = pd.to_datetime(combined["observed_at"], utc=True)

    # Group by city slug and year/month
    slug_col = "slug" if "slug" in combined.columns else "city_slug"
    if slug_col not in combined.columns:
        logger.error("Neither 'slug' nor 'city_slug' found in dataframe.")
        return

    for slug, group in combined.groupby(slug_col):
        # Deduplicate
        group = group.drop_duplicates(subset=[slug_col, "observed_at"], keep="last").sort_values("observed_at")
        year_str = target_date.strftime("%Y")
        month_str = target_date.strftime("%m")
        partition_key = f"processed/city={slug}/year={year_str}/month={month_str}/data.parquet"

        buffer = io.BytesIO()
        group.to_parquet(buffer, index=False, engine="pyarrow")
        buffer.seek(0)
        data = buffer.getvalue()

        logger.info("Writing compacted partition: s3://%s/%s (%d rows, %d bytes)",
                    S3_PROCESSED_BUCKET, partition_key, len(group), len(data))
        s3.put_object(
            Bucket=S3_PROCESSED_BUCKET,
            Key=partition_key,
            Body=data,
            ContentType="application/octet-stream",
        )

    logger.info("Compaction completed successfully.")


if __name__ == "__main__":
    compact_batches()
