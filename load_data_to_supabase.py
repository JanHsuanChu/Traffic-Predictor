# load_data_to_supabase.py
# Load traffic.csv and event.csv into Supabase traffic and event tables
# Pairs with SUPABASE_SETUP.md

# Reads local CSVs and inserts rows via the Supabase client.
# Loads SUPABASE_URL and SUPABASE_KEY from .env in this folder (or from environment).

# 0. Setup #################################

## 0.1 Load Packages ############################

import os
import pandas as pd
from pathlib import Path
from supabase import create_client

## 0.2 Load .env ###############################

# Load .env from the same directory as this script so we use URL/key saved there
_script_dir = Path(__file__).resolve().parent
_env_path = _script_dir / ".env"
if _env_path.exists():
    with open(_env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                key, value = key.strip(), value.strip().strip('"').strip("'")
                os.environ.setdefault(key, value)

## 0.3 Configuration ###############################

# Prefer SUPABASE_KEY; fall back to typo key SUPABSE_SERVICE_ROLE_KEY if present in .env
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABSE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise SystemExit(
        "Set SUPABASE_URL and SUPABASE_KEY in .env (or as environment variables). "
        "See SUPABASE_SETUP.md."
    )

# Batch size for inserts to avoid oversized requests
BATCH_SIZE = 500

# Run from script directory so traffic.csv and event.csv are found
os.chdir(_script_dir)

# 1. Connect to Supabase ###################################

client = create_client(SUPABASE_URL, SUPABASE_KEY)

# 2. Load and prepare traffic data ###################################

traffic_df = pd.read_csv("traffic.csv")
# Ensure types match DB: location_id and congestion_level as int; timestamps as strings (ISO)
traffic_df["location_id"] = traffic_df["location_id"].astype(int)
traffic_df["congestion_level"] = traffic_df["congestion_level"].astype(int)
# Keep traffic_timestamp and traffic_date as-is (already ISO-like)

# 3. Load and prepare event data ###################################

event_df = pd.read_csv("event.csv")
event_df["location_id"] = event_df["location_id"].astype(int)
if "event_duration" in event_df.columns:
    event_df["event_duration"] = event_df["event_duration"].astype(int)
# event_type, event_name, event_date, event_timestamp kept as-is

# 4. Insert traffic in batches ###################################

traffic_records = traffic_df.to_dict(orient="records")
for i in range(0, len(traffic_records), BATCH_SIZE):
    batch = traffic_records[i : i + BATCH_SIZE]
    client.table("traffic").insert(batch).execute()
    print(f"Inserted traffic rows {i + 1}–{min(i + BATCH_SIZE, len(traffic_records))} / {len(traffic_records)}")

print(f"Done: {len(traffic_records)} traffic rows.")

# 5. Insert events in batches ###################################

event_records = event_df.to_dict(orient="records")
for i in range(0, len(event_records), BATCH_SIZE):
    batch = event_records[i : i + BATCH_SIZE]
    client.table("event").insert(batch).execute()
    print(f"Inserted event rows {i + 1}–{min(i + BATCH_SIZE, len(event_records))} / {len(event_records)}")
print(f"Done: {len(event_records)} event rows.")
