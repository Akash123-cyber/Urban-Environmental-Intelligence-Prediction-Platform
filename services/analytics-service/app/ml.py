"""Inference-only model registry client and forecast feature helpers."""
from __future__ import annotations

import os
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any

import joblib
import numpy as np
import pandas as pd

TARGETS = {"pm25", "pm10"}
WX = ["temperature", "humidity", "wind_speed"]
FEATURES = ["lag_1", "lag_2", "lag_3", "lag_24", "roll_mean_6", "hour_sin", "hour_cos", "dow", *WX]


class ModelUnavailable(RuntimeError):
    """No accepted model is available for this city and target."""


@dataclass
class _CacheEntry:
    value: dict[str, Any] | None
    expires_at: float


class S3ModelRegistry:
    """Bounded lazy model cache with short negative caching; never trains models."""

    def __init__(
        self,
        bucket: str | None = None,
        prefix: str = "models/latest",
        region: str | None = None,
        cache_ttl_seconds: int = 900,
        negative_ttl_seconds: int = 60,
        max_entries: int = 128,
        s3_client: Any | None = None,
    ) -> None:
        self.bucket = bucket or os.getenv("S3_MODEL_BUCKET", "")
        self.prefix = prefix.strip("/")
        self.cache_ttl_seconds = max(1, cache_ttl_seconds)
        self.negative_ttl_seconds = max(1, negative_ttl_seconds)
        self.max_entries = max(1, max_entries)
        self._cache: OrderedDict[tuple[str, str], _CacheEntry] = OrderedDict()
        self._lock = threading.RLock()
        if s3_client is not None:
            self._s3 = s3_client
        else:
            import boto3
            self._s3 = boto3.client("s3", region_name=region or os.getenv("AWS_REGION"))

    @staticmethod
    def _validate(city_slug: str, target: str) -> None:
        if not city_slug or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789-" for c in city_slug):
            raise ValueError("city_slug must be a lowercase stable slug containing only a-z, 0-9, and hyphens")
        if target not in TARGETS:
            raise ValueError(f"target must be one of {sorted(TARGETS)}")

    def _key(self, city_slug: str, target: str) -> str:
        return f"{self.prefix}/{city_slug}_{target}.joblib"

    def get(self, city_slug: str, target: str) -> dict[str, Any]:
        self._validate(city_slug, target)
        if not self.bucket:
            raise ModelUnavailable("S3_MODEL_BUCKET is not configured")
        cache_key = (city_slug, target)
        now = time.monotonic()
        with self._lock:
            entry = self._cache.get(cache_key)
            if entry and entry.expires_at > now:
                self._cache.move_to_end(cache_key)
                if entry.value is None:
                    raise ModelUnavailable(f"no accepted model for {city_slug}/{target}")
                return entry.value
            if entry:
                del self._cache[cache_key]

        import io
        try:
            response = self._s3.get_object(Bucket=self.bucket, Key=self._key(city_slug, target))
            payload = response["Body"].read()
            bundle = joblib.load(io.BytesIO(payload))
            if not isinstance(bundle, dict) or "model" not in bundle or "version" not in bundle:
                raise ValueError("model bundle must be a dict containing model and version")
            if bundle.get("target", target) != target:
                raise ValueError("model bundle target does not match requested target")
        except Exception as exc:
            # Cache a missing key briefly, but do not disguise permission/network errors as a permanent absence.
            code = getattr(exc, "response", {}).get("Error", {}).get("Code", "")
            if code in {"NoSuchKey", "404", "NotFound"}:
                with self._lock:
                    self._put(cache_key, None, self.negative_ttl_seconds)
                raise ModelUnavailable(f"no accepted model for {city_slug}/{target}") from exc
            raise ModelUnavailable(f"model registry read failed for {city_slug}/{target}: {exc}") from exc

        with self._lock:
            self._put(cache_key, bundle, self.cache_ttl_seconds)
        return bundle

    def _put(self, key: tuple[str, str], value: dict[str, Any] | None, ttl: int) -> None:
        self._cache[key] = _CacheEntry(value=value, expires_at=time.monotonic() + ttl)
        self._cache.move_to_end(key)
        while len(self._cache) > self.max_entries:
            self._cache.popitem(last=False)

    def status(self) -> dict[str, Any]:
        return {"mode": "pretrained", "bucket_configured": bool(self.bucket), "cache_entries": len(self._cache)}


def prepare(df: pd.DataFrame) -> pd.DataFrame:
    """Build an hourly grid; only interpolate short interior gaps."""
    if df.empty or "observed_at" not in df.columns:
        return pd.DataFrame(columns=["pm25", "pm10", *WX])
    data = df.copy()
    data["observed_at"] = pd.to_datetime(data["observed_at"], utc=True)
    data = data.set_index("observed_at").sort_index()
    data = data[~data.index.duplicated(keep="last")]
    data = data.resample("1h").mean(numeric_only=True)
    for col in ["pm25", "pm10", *WX]:
        if col not in data:
            data[col] = np.nan
    return data.interpolate(limit=6, limit_area="inside")


def make_features(df: pd.DataFrame, target: str) -> pd.DataFrame:
    if target not in TARGETS:
        raise ValueError(f"target must be one of {sorted(TARGETS)}")
    series = df[target]
    x = pd.DataFrame(index=df.index)
    for lag in (1, 2, 3, 24):
        x[f"lag_{lag}"] = series.shift(lag)
    x["roll_mean_6"] = series.shift(1).rolling(6).mean()
    x["hour_sin"] = np.sin(2 * np.pi * df.index.hour / 24)
    x["hour_cos"] = np.cos(2 * np.pi * df.index.hour / 24)
    x["dow"] = df.index.dayofweek
    for col in WX:
        x[col] = df[col] if col in df else np.nan
    return x[FEATURES]


def forecast(bundle: dict[str, Any], df: pd.DataFrame, target: str, steps: int = 24) -> list[tuple[pd.Timestamp, float]]:
    """Recursive forecast. Future weather is held at the latest observed values."""
    if steps < 1 or steps > 72:
        raise ValueError("steps must be between 1 and 72")
    if df.empty or target not in df or df[target].dropna().empty:
        raise ValueError("not enough observations to forecast")
    hist = df.reindex(columns=[target, *WX]).copy().tail(120)
    last_valid = hist[target].last_valid_index()
    if last_valid is None:
        raise ValueError("target has no valid observations")
    hist = hist.loc[:last_valid]
    wx = hist[WX].ffill().iloc[-1].fillna(0.0).tolist()
    result: list[tuple[pd.Timestamp, float]] = []
    for _ in range(steps):
        next_time = hist.index[-1] + pd.Timedelta(hours=1)
        hist.loc[next_time] = [np.nan, *wx]
        row = make_features(hist, target).iloc[[-1]]
        if row.isna().any(axis=None):
            raise ValueError("feature row contains missing values; more history is required")
        prediction = max(float(bundle["model"].predict(row)[0]), 0.0)
        hist.loc[next_time, target] = prediction
        result.append((next_time, prediction))
    return result
