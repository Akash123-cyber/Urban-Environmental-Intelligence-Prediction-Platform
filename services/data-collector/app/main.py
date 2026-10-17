import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import uuid

import httpx
from fastapi import FastAPI, BackgroundTasks, Response
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from .config import settings, load_cities
from .sources import (
    plan_cycle,
    fetch_open_meteo_air,
    fetch_open_meteo_weather,
    COLLECTOR_CYCLE_DURATION_SECONDS,
)

logging.basicConfig(level=settings.LOG_LEVEL, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("collector.main")

poller_task = None


async def run_collection_cycle(target_city_slug: str | None = None, force: bool = False):
    with COLLECTOR_CYCLE_DURATION_SECONDS.time():
        cycle_id = f"cycle_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        logger.info("Starting collection cycle: %s (target=%s, force=%s)", cycle_id, target_city_slug, force)

        all_cities = load_cities()
        if not all_cities:
            logger.warning("No cities loaded. Skipping cycle.")
            return {"status": "skipped", "reason": "no cities"}

        cities = [c for c in all_cities if c["slug"] == target_city_slug] if target_city_slug else all_cities

        async with httpx.AsyncClient(timeout=30.0) as client:
            # 1. Fetch current freshness from processor (only if not forcing)
            latest_map = {}
            if not force:
                try:
                    resp = await client.get(f"{settings.PROCESSOR_URL}/latest")
                    if resp.status_code == 200:
                        latest_map = resp.json()
                    else:
                        logger.warning("Processor /latest returned HTTP %d", resp.status_code)
                except Exception as exc:
                    logger.warning("Could not reach processor at %s/latest: %s", settings.PROCESSOR_URL, exc)

            # 2. Plan due cities
            due_cities = cities if force else plan_cycle(cities, latest_map, settings.LIVE_LOOKBACK_HOURS, force=force)
            logger.info("Due cities for fetch: %d / %d", len(due_cities), len(cities))

            if not due_cities:
                logger.info("All cities are up to date. Cycle %s is idle.", cycle_id)
                return {"status": "idle", "cycle_id": cycle_id}

            # 3. Collect observations for due cities
            batch_items = []
            for city in due_cities:
                air_data = await fetch_open_meteo_air(
                    client, city["latitude"], city["longitude"], settings.LIVE_LOOKBACK_HOURS
                )
                wx_data = await fetch_open_meteo_weather(
                    client, city["latitude"], city["longitude"], settings.LIVE_LOOKBACK_HOURS
                )

                batch_items.append({
                    "city": city,
                    "air": air_data,
                    "weather": wx_data,
                })

            # 4. Ship batch payload to processor
            payload = {
                "cycle_id": cycle_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "items": batch_items,
            }

            try:
                ingest_resp = await client.post(
                    f"{settings.PROCESSOR_URL}/ingest",
                    json=payload,
                    timeout=60.0,
                )
                if ingest_resp.status_code in (200, 201):
                    res_data = ingest_resp.json()
                    logger.info("Cycle %s successfully ingested by processor: %s", cycle_id, res_data)
                    return {"status": "success", "cycle_id": cycle_id, "ingested": res_data}
                else:
                    logger.error("Processor /ingest returned status %d: %s", ingest_resp.status_code, ingest_resp.text)
                    return {"status": "error", "error": ingest_resp.text}
            except Exception as exc:
                logger.error("Failed sending batch to processor: %s", exc)
                return {"status": "error", "error": str(exc)}


async def poll_scheduler():
    logger.info("Collector scheduler started (interval: %d s)", settings.POLL_INTERVAL_SECONDS)
    while True:
        try:
            await run_collection_cycle()
        except Exception as exc:
            logger.error("Unhandled error in collection cycle: %s", exc, exc_info=True)
        await asyncio.sleep(settings.POLL_INTERVAL_SECONDS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global poller_task
    poller_task = asyncio.create_task(poll_scheduler())
    yield
    if poller_task:
        poller_task.cancel()
        try:
            await poller_task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="Urban EIPP Data Collector", version="1.0.0", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "healthy", "service": "data-collector", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.get("/ready")
def ready():
    return {"status": "ready", "service": "data-collector"}


@app.get("/metrics")
def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/poll")
async def trigger_poll(city: str | None = None, force: bool = False, sync: bool = True):
    if sync:
        res = await run_collection_cycle(target_city_slug=city, force=force)
        return res
    else:
        asyncio.create_task(run_collection_cycle(target_city_slug=city, force=force))
        return {"message": "Collection cycle scheduled"}
