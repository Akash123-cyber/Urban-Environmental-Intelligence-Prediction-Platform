"""Single-leader periodic forecast cycle; no training fallback."""
from __future__ import annotations

import asyncio
import logging
import os
from sqlalchemy import text

from . import ml, repo

log = logging.getLogger("urban-eipp.analytics.scheduler")
LOCK_KEY = 72419031
INTERVAL_SECONDS = max(60, int(os.getenv("ANALYTICS_INTERVAL_SECONDS", "1800")))


def run_cycle(registry) -> list[dict]:
    engine = repo.require_engine()
    results: list[dict] = []
    # Session-level lock is held on this connection throughout the cycle.
    with engine.connect() as lock_conn:
        acquired = lock_conn.execute(text("SELECT pg_try_advisory_lock(:key)"), {"key": LOCK_KEY}).scalar()
        lock_conn.commit()
        if not acquired:
            return [{"status": "skipped", "reason": "another replica owns the analytics lock"}]
        try:
            for city in repo.list_cities():
                city_id, slug = city["id"], city["slug"]
                try:
                    newest = repo.latest_measurement_time(city_id)
                    if newest is None:
                        results.append({"city": slug, "status": "skipped", "reason": "no observations"})
                        continue
                    previous = repo.latest_prediction_based_on(city_id)
                    if previous is not None and previous >= newest:
                        results.append({"city": slug, "status": "idle", "based_on": newest.isoformat()})
                        continue
                    raw = repo.load_series(city_id)
                    df = ml.prepare(raw)
                    if len(df) < 72:
                        results.append({"city": slug, "status": "skipped", "reason": "insufficient observations"})
                        continue
                    forecasts, versions = {}, []
                    for target in ("pm25", "pm10"):
                        bundle = registry.get(slug, target)
                        forecasts[target] = dict(ml.forecast(bundle, df, target, 24))
                        versions.append(str(bundle["version"]))
                    times = sorted(forecasts["pm25"])
                    rows = [{
                        "target_time": stamp.to_pydatetime(),
                        "predicted_pm25": forecasts["pm25"].get(stamp),
                        "predicted_pm10": forecasts["pm10"].get(stamp),
                        "model_version": ",".join(sorted(set(versions))),
                    } for stamp in times]
                    repo.save_predictions(city_id, newest, rows)
                    results.append({"city": slug, "status": "forecasted", "rows": len(rows), "based_on": newest.isoformat()})
                except ml.ModelUnavailable as exc:
                    log.warning("model unavailable city=%s detail=%s", slug, exc)
                    results.append({"city": slug, "status": "model_unavailable"})
                except Exception as exc:
                    log.exception("analytics cycle failed for city=%s", slug)
                    results.append({"city": slug, "status": "error", "detail": str(exc)})
            return results
        finally:
            lock_conn.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": LOCK_KEY})
            lock_conn.commit()


async def loop(registry):
    await asyncio.sleep(15)
    while True:
        try:
            result = await asyncio.to_thread(run_cycle, registry)
            log.info("analytics cycle result=%s", result)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("analytics cycle crashed")
        await asyncio.sleep(INTERVAL_SECONDS)
