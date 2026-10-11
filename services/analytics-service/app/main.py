"""FastAPI endpoints for inference-only production analytics."""
from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Query
try:
    from prometheus_fastapi_instrumentator import Instrumentator
except ImportError:  # Allows local unit tests/minimal mode; production requirements include it.
    Instrumentator = None
from sqlalchemy import text

from . import ml, repo, scheduler

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
log = logging.getLogger("urban-eipp.analytics")
USE_PRETRAINED = os.getenv("USE_PRETRAINED", "true").lower() == "true"
registry = ml.S3ModelRegistry()
@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(scheduler.loop(registry)) if os.getenv("ENABLE_SCHEDULER", "true").lower() == "true" else None
    try:
        yield
    finally:
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass


app = FastAPI(title="Urban EIPP Analytics", version="0.1.0", lifespan=lifespan)
if Instrumentator is not None:
    Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)
else:
    log.warning("Prometheus instrumentation dependency missing; /metrics is disabled")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/ready")
def ready():
    try:
        with repo.require_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(status_code=503, detail="database unavailable") from exc
    if not registry.bucket:
        raise HTTPException(status_code=503, detail="S3_MODEL_BUCKET is not configured")
    return {"status": "ready", "model_registry": registry.status()}


@app.get("/models")
def models():
    return {**registry.status(), "training_enabled": False, "training_location": "offline Colab workflow"}


@app.post("/train")
def train_disabled():
    if USE_PRETRAINED:
        raise HTTPException(status_code=403, detail="production analytics is inference-only; train models offline")
    raise HTTPException(status_code=501, detail="local training is not implemented in this production service")


def _city(city_slug: str) -> dict:
    try:
        cities = repo.list_cities()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="database unavailable") from exc
    for city in cities:
        if city["slug"] == city_slug:
            return city
    raise HTTPException(status_code=404, detail="unknown city slug")


@app.get("/forecast/{city_slug}")
def get_forecast(city_slug: str, hours: int = Query(24, ge=1, le=72)):
    city = _city(city_slug)
    try:
        raw = repo.load_series(city["id"])
        df = ml.prepare(raw)
        if len(df) < 72:
            raise HTTPException(status_code=409, detail="forecast not available yet: insufficient observations")
        target_history = df[["pm25", "pm10"]].dropna(how="all")
        if target_history.empty:
            raise HTTPException(status_code=409, detail="forecast not available yet: no PM observations")
        newest_observation = target_history.index.max()
        previous_forecast = repo.latest_prediction_based_on(city["id"])
        if previous_forecast is not None and previous_forecast >= newest_observation.to_pydatetime():
            return {"city": city_slug, "based_on": previous_forecast.isoformat(), "forecast": repo.get_predictions(city["id"], hours)}
        forecasts = {}
        versions = []
        for target in ("pm25", "pm10"):
            bundle = registry.get(city_slug, target)
            forecasts[target] = dict(ml.forecast(bundle, df, target, hours))
            versions.append(str(bundle["version"]))
        times = sorted(forecasts["pm25"])
        rows = [{"target_time": t.isoformat(), "predicted_pm25": forecasts["pm25"].get(t),
                 "predicted_pm10": forecasts["pm10"].get(t), "model_version": ",".join(sorted(set(versions)),),
                 "based_on": newest_observation.isoformat()} for t in times]
        repo.save_predictions(city["id"], newest_observation.to_pydatetime(), rows)
        return {"city": city_slug, "based_on": newest_observation.isoformat(), "forecast": rows}
    except HTTPException:
        raise
    except ml.ModelUnavailable as exc:
        log.warning("forecast unavailable city=%s reason=%s", city_slug, exc)
        raise HTTPException(status_code=503, detail=f"forecast not available yet: {exc}") from exc
    except Exception as exc:
        log.exception("forecast failed city=%s", city_slug)
        raise HTTPException(status_code=500, detail="forecast processing failed") from exc
