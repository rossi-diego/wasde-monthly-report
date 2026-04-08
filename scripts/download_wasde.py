"""Download WASDE CSVs for 2024-01 through 2026-03."""

import time
from pathlib import Path

import requests

OUTPUT_DIR = Path("data/bronze/wasde")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

BASE_URL = "https://www.usda.gov/sites/default/files/documents/oce-wasde-report-data-{year}-{month:02d}.csv"

months = []
for y in range(2024, 2027):
    end_m = 3 if y == 2026 else 12
    for m in range(1, end_m + 1):
        months.append((y, m))

for year, month in months:
    out = OUTPUT_DIR / f"wasde_{year}_{month:02d}.csv"
    if out.exists() and out.stat().st_size > 100:
        print(f"  CACHED {out.name}")
        continue

    url = BASE_URL.format(year=year, month=month)
    for attempt in range(3):
        try:
            print(f"  Downloading {year}-{month:02d} (attempt {attempt + 1})...", end=" ", flush=True)
            resp = requests.get(url, timeout=60)
            if resp.status_code == 200 and len(resp.content) > 100:
                out.write_bytes(resp.content)
                print(f"OK ({len(resp.content)} bytes)")
                break
            else:
                print(f"HTTP {resp.status_code}")
                break  # Don't retry 404s
        except requests.Timeout:
            print("TIMEOUT")
            time.sleep(5 * (attempt + 1))
        except Exception as e:
            print(f"ERROR: {e}")
            break

print("\nDone. Files in", OUTPUT_DIR)
for f in sorted(OUTPUT_DIR.glob("*.csv")):
    print(f"  {f.name} ({f.stat().st_size:,} bytes)")
