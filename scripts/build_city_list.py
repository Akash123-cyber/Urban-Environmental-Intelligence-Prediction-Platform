#!/usr/bin/env python3
"""
Validates and normalizes canonical city list for the Urban Environmental Intelligence Platform.
Ensures slugs are unique, lower-case, url-safe, and coordinates are valid.
"""
import csv
import re
import sys
from pathlib import Path

CITIES_CSV = Path(__file__).resolve().parent.parent / "data" / "cities.csv"


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def main():
    if not CITIES_CSV.exists():
        print(f"Error: {CITIES_CSV} not found", file=sys.stderr)
        sys.exit(1)

    seen_slugs = set()
    rows = []
    has_errors = False

    with open(CITIES_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        required_cols = {"slug", "name", "state", "country", "latitude", "longitude"}
        if not required_cols.issubset(set(reader.fieldnames or [])):
            print(f"Error: Missing required columns in {CITIES_CSV}. Required: {required_cols}", file=sys.stderr)
            sys.exit(1)

        for line_num, row in enumerate(reader, start=2):
            slug = row["slug"].strip()
            name = row["name"].strip()
            state = row["state"].strip()
            country = row["country"].strip()
            lat_str = row["latitude"].strip()
            lon_str = row["longitude"].strip()

            if not slug:
                slug = slugify(name)
                row["slug"] = slug

            if slug in seen_slugs:
                print(f"Error line {line_num}: Duplicate slug '{slug}'", file=sys.stderr)
                has_errors = True
            seen_slugs.add(slug)

            try:
                lat = float(lat_str)
                lon = float(lon_str)
                if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                    print(f"Error line {line_num}: Coordinates out of range ({lat}, {lon})", file=sys.stderr)
                    has_errors = True
            except ValueError:
                print(f"Error line {line_num}: Invalid float coordinates ({lat_str}, {lon_str})", file=sys.stderr)
                has_errors = True

            rows.append(row)

    if has_errors:
        print("Validation FAILED.", file=sys.stderr)
        sys.exit(1)

    print(f"Successfully validated {len(rows)} cities in {CITIES_CSV}.")


if __name__ == "__main__":
    main()
