import io
import json
import logging
from datetime import datetime, timezone
import boto3
import pandas as pd
from .config import settings

logger = logging.getLogger("processor.s3")


def get_s3_client():
    kwargs = {
        "region_name": settings.AWS_REGION,
    }
    if settings.S3_ENDPOINT_URL:
        kwargs["endpoint_url"] = settings.S3_ENDPOINT_URL
    if settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
        kwargs["aws_access_key_id"] = settings.AWS_ACCESS_KEY_ID
        kwargs["aws_secret_access_key"] = settings.AWS_SECRET_ACCESS_KEY
    return boto3.client("s3", **kwargs)


def archive_raw_batch(cycle_id: str, payload: dict) -> str:
    """Writes raw batch json to S3 raw bucket: raw/YYYY/MM/DD/batch_<cycle_id>.json"""
    client = get_s3_client()
    now = datetime.now(timezone.utc)
    key = f"raw/{now:%Y/%m/%d}/batch_{cycle_id}.json"
    body = json.dumps(payload, default=str).encode("utf-8")

    logger.info("Archiving raw batch to s3://%s/%s (%d bytes)", settings.S3_RAW_BUCKET, key, len(body))
    client.put_object(
        Bucket=settings.S3_RAW_BUCKET,
        Key=key,
        Body=body,
        ContentType="application/json",
    )
    return key


def archive_processed_parquet(cycle_id: str, df: pd.DataFrame) -> str:
    """Writes normalized parquet batch to S3 processed bucket: processed/batches/YYYY/MM/DD/batch_<cycle_id>.parquet"""
    client = get_s3_client()
    now = datetime.now(timezone.utc)
    key = f"processed/batches/{now:%Y/%m/%d}/batch_{cycle_id}.parquet"

    buffer = io.BytesIO()
    df.to_parquet(buffer, index=False, engine="pyarrow")
    buffer.seek(0)
    parquet_bytes = buffer.getvalue()

    logger.info("Archiving processed parquet to s3://%s/%s (%d bytes)", settings.S3_PROCESSED_BUCKET, key, len(parquet_bytes))
    client.put_object(
        Bucket=settings.S3_PROCESSED_BUCKET,
        Key=key,
        Body=parquet_bytes,
        ContentType="application/octet-stream",
    )
    return key
