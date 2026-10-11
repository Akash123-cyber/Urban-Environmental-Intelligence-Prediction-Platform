"""Offline model training and S3/MinIO publishing script.

This script trains XGBoost models for each city and target (PM2.5, PM10) using
historical data bootstrapped from Open-Meteo and/or S3 Parquet partitions.
It enforces the deployment gate (skill_vs_persistence > 0) and publishes
joblib bundles to S3 / MinIO under `models/<version>/` and `models/latest/`.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import platform
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import boto3
import joblib
import numpy as np
import pandas as pd
import requests
import sklearn
import xgboost
from scipy.stats import randint, uniform
from sklearn.metrics import mean_absolute_error, root_mean_squared_error
from sklearn.model_selection import RandomizedSearchCV, TimeSeriesSplit
from xgboost import XGBRegressor

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "analytics-service"))

from app.ml import FEATURES, TARGETS, WX, make_features, prepare

AIR_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
WX_URL = "https://archive-api.open-meteo.com/v1/archive"
AIR_MAP = {
    "pm2_5": "pm25",
    "pm10": "pm10",
    "nitrogen_dioxide": "no2",
    "ozone": "o3",
    "carbon_monoxide": "co",
    "sulphur_dioxide": "so2",
}
WX_MAP = {
    "temperature_2m": "temperature",
    "relative_humidity_2m": "humidity",
    "wind_speed_10m": "wind_speed",
}

SEARCH_SPACE = {
    "n_estimators": randint(80, 250),
    "max_depth": randint(3, 6),
    "learning_rate": uniform(0.04, 0.10),
    "subsample": uniform(0.7, 0.3),
    "colsample_bytree": uniform(0.7, 0.3),
    "reg_lambda": uniform(0.5, 3.0),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train urban air quality forecasting models.")
    parser.add_argument("--cities-csv", default=str(ROOT / "data" / "cities.csv"))
    parser.add_argument("--days", type=int, default=30, help="Days of historical training data")
    parser.add_argument("--n-iter", type=int, default=8, help="Randomized search CV iterations")
    parser.add_argument("--out-dir", default=str(ROOT / "data" / "models"))
    parser.add_argument("--s3-bucket", default=os.getenv("S3_MODEL_BUCKET", "urban-models"))
    parser.add_argument("--s3-endpoint", default=os.getenv("S3_ENDPOINT_URL", ""))
    parser.add_argument("--aws-region", default=os.getenv("AWS_REGION", "us-east-1"))
    parser.add_argument("--upload", action="store_true", help="Upload trained models to S3/MinIO")
    return parser.parse_args()


def fetch_hourly(url: str, lat: float, lon: float, mapping: dict[str, str], start_date: date, end_date: date) -> dict:
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": ",".join(mapping.keys()),
        "start_date": str(start_date),
        "end_date": str(end_date),
        "timezone": "UTC",
    }
    try:
        res = requests.get(url, params=params, timeout=30)
        if res.status_code != 200:
            return {}
        data = res.json().get("hourly", {})
        times = data.get("time", [])
        return {
            t: {dest: data[src][i] for src, dest in mapping.items() if src in data}
            for i, t in enumerate(times)
        }
    except Exception:
        return {}


def bootstrap_city(lat: float, lon: float, days: int = 30) -> pd.DataFrame:
    end_dt = date.today() - timedelta(days=2)
    start_dt = end_dt - timedelta(days=days)
    air = fetch_hourly(AIR_URL, lat, lon, AIR_MAP, start_dt, end_dt)
    wx = fetch_hourly(WX_URL, lat, lon, WX_MAP, start_dt, end_dt)
    all_times = sorted(set(air.keys()) | set(wx.keys()))
    records = [{"observed_at": t + "Z", **air.get(t, {}), **wx.get(t, {})} for t in all_times]
    return pd.DataFrame(records)


def train_target(df: pd.DataFrame, target: str, n_iter: int = 8):
    X = make_features(df, target)
    y = df[target]
    valid = y.notna() & X["lag_1"].notna()
    X_val, y_val = X[valid], y[valid]

    n = len(X_val)
    i1, i2 = int(n * 0.70), int(n * 0.85)
    X_tr, y_tr = X_val.iloc[:i1], y_val.iloc[:i1]
    X_va, y_va = X_val.iloc[i1:i2], y_val.iloc[i1:i2]
    X_te, y_te = X_val.iloc[i2:], y_val.iloc[i2:]

    X_train_val = pd.concat([X_tr, X_va])
    y_train_val = pd.concat([y_tr, y_va])

    search = RandomizedSearchCV(
        XGBRegressor(n_jobs=1, random_state=42),
        SEARCH_SPACE,
        n_iter=n_iter,
        cv=TimeSeriesSplit(n_splits=3),
        scoring="neg_mean_absolute_error",
        random_state=42,
        refit=False,
    )
    search.fit(X_train_val, y_train_val)
    best_params = search.best_params_

    eval_model = XGBRegressor(**best_params, n_jobs=1, random_state=42).fit(X_train_val, y_train_val)
    test_preds = eval_model.predict(X_te)

    mae = float(mean_absolute_error(y_te, test_preds))
    rmse = float(root_mean_squared_error(y_te, test_preds))
    p_mae = float(mean_absolute_error(y_te, X_te["lag_1"]))

    final_model = XGBRegressor(**best_params, n_jobs=1, random_state=42).fit(X_val, y_val)

    return final_model, {
        "params": best_params,
        "mae": mae,
        "rmse": rmse,
        "persistence_mae": p_mae,
        "rows": len(X_val),
    }


def main() -> int:
    args = parse_args()
    cities_path = Path(args.cities_csv)
    if not cities_path.exists():
        print(f"Error: {cities_path} not found")
        return 1

    cities_df = pd.read_csv(cities_path)
    version = datetime.now(timezone.utc).strftime("%Y%m%d%H%M")
    out_dir = Path(args.out_dir) / version
    out_dir.mkdir(parents=True, exist_ok=True)

    libs = {
        "python": platform.python_version(),
        "pandas": pd.__version__,
        "numpy": np.__version__,
        "scikit-learn": sklearn.__version__,
        "xgboost": xgboost.__version__,
    }

    manifest = {
        "version": version,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "features": FEATURES,
        "libraries": libs,
        "models": {},
    }

    print(f"Training models for {len(cities_df)} cities (version {version})...")

    for _, row in cities_df.iterrows():
        slug = str(row["slug"])
        name = str(row["name"])
        lat = float(row["latitude"])
        lon = float(row["longitude"])

        print(f"\nProcessing {name} ({slug})...")
        raw = bootstrap_city(lat, lon, days=args.days)
        if raw.empty:
            print(f"  Warning: No data for {slug}, skipping")
            continue

        raw["observed_at"] = pd.to_datetime(raw["observed_at"], utc=True)
        raw = raw.drop_duplicates("observed_at", keep="last").sort_values("observed_at")
        grid = prepare(raw)

        if len(grid) < 72:
            print(f"  Warning: Insufficient hourly observations ({len(grid)}h), skipping")
            continue

        for target in ["pm25", "pm10"]:
            if target not in grid or grid[target].dropna().empty:
                continue
            model, res = train_target(grid, target, n_iter=args.n_iter)
            skill = 1.0 - (res["mae"] / res["persistence_mae"]) if res["persistence_mae"] > 0 else 0.0

            if skill <= 0.0:
                print(f"  {target.upper()}: gate failed (MAE {res['mae']:.2f} >= Persist {res['persistence_mae']:.2f})")
                continue

            print(f"  {target.upper()}: ACCEPTED (MAE {res['mae']:.2f} vs Persist {res['persistence_mae']:.2f}, Skill: {skill*100:.1f}%)")

            bundle = {
                "model": model,
                "version": version,
                "trained_at": time.time(),
                "target": target,
                "metrics": {"mae": res["mae"], "rmse": res["rmse"], "persistence_mae": res["persistence_mae"]},
                "params": res["params"],
                "data_range": [str(grid.index.min()), str(grid.index.max())],
                "libraries": libs,
            }

            key = f"{slug}_{target}"
            bundle_path = out_dir / f"{key}.joblib"
            joblib.dump(bundle, bundle_path)
            model.save_model(str(out_dir / f"{key}.json"))

            manifest["models"][key] = {
                "metrics": bundle["metrics"],
                "data_range": bundle["data_range"],
            }

    with open(out_dir / "manifest.json", "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"\nArtifacts generated in: {out_dir}")
    print(f"Accepted models: {len(manifest['models'])}")

    if args.upload and manifest["models"]:
        s3_kwargs = {"region_name": args.aws_region}
        if args.s3_endpoint:
            s3_kwargs["endpoint_url"] = args.s3_endpoint
        ak = os.getenv("AWS_ACCESS_KEY_ID")
        sk = os.getenv("AWS_SECRET_ACCESS_KEY")
        if ak and sk:
            s3_kwargs["aws_access_key_id"] = ak
            s3_kwargs["aws_secret_access_key"] = sk
        s3 = boto3.client("s3", **s3_kwargs)

        print(f"Publishing artifacts to S3 bucket '{args.s3_bucket}'...")
        for file_path in out_dir.iterdir():
            if file_path.is_file():
                s3.upload_file(str(file_path), args.s3_bucket, f"models/{version}/{file_path.name}")
                s3.upload_file(str(file_path), args.s3_bucket, f"models/latest/{file_path.name}")
                print(f"  Uploaded: {file_path.name} -> models/latest/{file_path.name}")
        print("Model publication complete.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
