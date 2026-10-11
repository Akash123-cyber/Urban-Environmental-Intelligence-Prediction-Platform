import csv
import logging
import os
from pathlib import Path
from pydantic_settings import BaseSettings

logger = logging.getLogger("collector.config")


class Settings(BaseSettings):
    PROCESSOR_URL: str = os.getenv("PROCESSOR_URL", "http://data-processor:5000")
    POLL_INTERVAL_SECONDS: int = int(os.getenv("POLL_INTERVAL_SECONDS", "900"))
    LIVE_LOOKBACK_HOURS: int = int(os.getenv("LIVE_LOOKBACK_HOURS", "2"))
    OPENAQ_API_KEY: str = os.getenv("OPENAQ_API_KEY", "")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    CITIES_CSV_PATH: str = os.getenv("CITIES_CSV_PATH", "data/cities.csv")

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()


def load_cities(csv_path: str = None) -> list[dict]:
    path = Path(csv_path or settings.CITIES_CSV_PATH)
    if not path.is_absolute():
        # Check relative to cwd or root
        candidates = [path, Path(__file__).resolve().parent.parent.parent.parent / path]
        for c in candidates:
            if c.exists():
                path = c
                break

    cities = []
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                cities.append({
                    "slug": row["slug"].strip(),
                    "name": row["name"].strip(),
                    "state": row.get("state", "").strip(),
                    "country": row.get("country", "India").strip(),
                    "latitude": float(row["latitude"]),
                    "longitude": float(row["longitude"]),
                })
        logger.info("Loaded %d cities from %s", len(cities), path)
    else:
        # Fallback default seeds
        logger.warning("Cities CSV not found at %s. Using default fallback list.", path)
        cities = [
            {"slug": "delhi", "name": "Delhi", "state": "Delhi", "country": "India", "latitude": 28.6139, "longitude": 77.2090},
            {"slug": "mumbai", "name": "Mumbai", "state": "Maharashtra", "country": "India", "latitude": 19.0760, "longitude": 72.8777},
            {"slug": "kolkata", "name": "Kolkata", "state": "West Bengal", "country": "India", "latitude": 22.5726, "longitude": 88.3639},
            {"slug": "chennai", "name": "Chennai", "state": "Tamil Nadu", "country": "India", "latitude": 13.0827, "longitude": 80.2707},
            {"slug": "bengaluru", "name": "Bengaluru", "state": "Karnataka", "country": "India", "latitude": 12.9716, "longitude": 77.5946},
        ]
    return cities
