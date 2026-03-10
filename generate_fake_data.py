# generate_fake_data.py
# Generate fake traffic and event tables for Traffic-Predictor
# Pairs with workflow-diagram.md and future database load

# Generates 50000 traffic records and 1000 event records (Jan 2024–Dec 2025).
# Traffic is biased so many rows share (location_id, date) with events for easier matching.
# Events include event_duration (minutes). Event names are short descriptions (≤15 words) by type.

# 0. Setup #################################

## 0.1 Load Packages ############################

import pandas as pd
import numpy as np
from datetime import datetime, timedelta

## 0.2 Parameters ###############################

# Date range: January 2024 to December 2025
START_DATE = datetime(2024, 1, 1)
END_DATE = datetime(2025, 12, 31)
NUM_TRAFFIC = 50000
NUM_EVENTS = 1000
# Location IDs 1–50 shared across traffic and events (for joins)
LOCATION_IDS = list(range(1, 51))
# Traffic rows to generate per event on the same (location_id, date) for guaranteed overlap
TRAFFIC_PER_EVENT_DATE = 40
# Event duration: min and max in minutes
EVENT_DURATION_MIN = 30
EVENT_DURATION_MAX = 480

# 1. Event name pools (≤15 words each) ###################################

EVENT_NAMES_BY_TYPE = {
    "Sport & cultural": [
        "Taylor Swift Era Tour",
        "MLB World Championship",
        "FIFA World Cup",
        "Super Bowl LIX",
        "Olympics Paris 2024",
        "Coachella Music Festival",
        "NBA Finals",
        "Wimbledon Championship",
        "Met Gala",
        "Broadway opening night",
        "Local marathon",
        "Jazz festival downtown",
        "Art fair weekend",
        "Comic Con",
        "Christmas parade",
    ],
    "holiday": [
        "Thanksgiving",
        "New Year Eve",
        "Christmas Day",
        "Independence Day",
        "Memorial Day",
        "Labor Day",
        "Black Friday",
        "Easter Sunday",
        "Halloween",
        "Valentine's Day",
        "St Patrick's Day parade",
        "Diwali festival",
        "Chinese New Year",
    ],
    "weather": [
        "Snowstorm",
        "Heavy rain and flooding",
        "Heat wave advisory",
        "Ice storm",
        "Hurricane warning",
        "Blizzard",
        "Thunderstorm and power outage",
        "Fog advisory",
        "Wildfire smoke",
        "Dust storm",
    ],
    "emergency": [
        "2025 LA Fire",
        "Building collapse",
        "Major power outage",
        "Gas leak evacuation",
        "Bridge closure",
        "Highway accident",
        "Protest downtown",
        "Security incident",
        "Water main break",
        "Train derailment",
    ],
}

# 2. Helpers ###############################

def random_datetime(start: datetime, end: datetime, rng: np.random.Generator) -> datetime:
    """Draw a random datetime between start and end."""
    delta = end - start
    total_seconds = int(delta.total_seconds())
    if total_seconds <= 0:
        return start
    sec = int(rng.integers(0, total_seconds))
    return start + timedelta(seconds=sec)


def random_time_on_date(d: datetime, rng: np.random.Generator) -> datetime:
    """Random time on the given date (midnight to 23:59:59)."""
    start = datetime(d.year, d.month, d.day, 0, 0, 0)
    end = datetime(d.year, d.month, d.day, 23, 59, 59)
    return random_datetime(start, end, rng)


# 3. Generate Event Table (with event_duration) ###################################

def generate_events(
    n: int,
    start: datetime,
    end: datetime,
    location_ids: list,
    seed: int = 43,
) -> pd.DataFrame:
    """Generate n event records with event_type, event_name, date, timestamp, event_duration (minutes)."""
    rng = np.random.default_rng(seed)
    event_types = list(EVENT_NAMES_BY_TYPE.keys())
    rows = []
    for _ in range(n):
        ts = random_datetime(start, end, rng)
        event_date = ts.date().isoformat()
        event_timestamp = ts.isoformat(sep=" ")
        location_id = int(rng.choice(location_ids))
        event_type = rng.choice(event_types)
        event_name = rng.choice(EVENT_NAMES_BY_TYPE[event_type])
        event_duration = int(rng.integers(EVENT_DURATION_MIN, EVENT_DURATION_MAX + 1))
        rows.append({
            "location_id": location_id,
            "event_type": event_type,
            "event_name": event_name,
            "event_date": event_date,
            "event_timestamp": event_timestamp,
            "event_duration": event_duration,
        })
    return pd.DataFrame(rows)


# 4. Generate Traffic Table (biased to match event dates/locations) ###################################

def generate_traffic(
    n: int,
    events_df: pd.DataFrame,
    start: datetime,
    end: datetime,
    location_ids: list,
    traffic_per_event: int,
    seed: int = 42,
) -> pd.DataFrame:
    """
    Generate n traffic records. For each event we add traffic_per_event rows on the same
    (location_id, event_date) so traffic and events match. Remaining rows are random.
    """
    rng = np.random.default_rng(seed)
    rows = []

    # 4.1 Traffic on same (location_id, date) as each event -> high overlap
    event_dates_by_loc = set()
    for _, ev in events_df.iterrows():
        loc = int(ev["location_id"])
        ed = ev["event_date"]  # already YYYY-MM-DD string
        event_dates_by_loc.add((loc, ed))
        d = datetime.strptime(ed, "%Y-%m-%d")
        for _ in range(traffic_per_event):
            ts = random_time_on_date(d, rng)
            traffic_date = ts.date().isoformat()
            traffic_timestamp = ts.isoformat(sep=" ")
            congestion_level = int(rng.integers(1, 11))
            rows.append({
                "location_id": loc,
                "traffic_timestamp": traffic_timestamp,
                "traffic_date": traffic_date,
                "congestion_level": congestion_level,
            })

    n_matched = len(rows)
    n_extra = n - n_matched
    if n_extra < 0:
        rows = rows[:n]
    else:
        # 4.2 Fill remaining with random traffic (spread over locations and dates)
        for _ in range(n_extra):
            ts = random_datetime(start, end, rng)
            traffic_date = ts.date().isoformat()
            traffic_timestamp = ts.isoformat(sep=" ")
            location_id = int(rng.choice(location_ids))
            congestion_level = int(rng.integers(1, 11))
            rows.append({
                "location_id": location_id,
                "traffic_timestamp": traffic_timestamp,
                "traffic_date": traffic_date,
                "congestion_level": congestion_level,
            })

    return pd.DataFrame(rows)


# 5. Generate and save CSVs ###################################

if __name__ == "__main__":
    out_dir = "."
    traffic_path = f"{out_dir}/traffic.csv"
    event_path = f"{out_dir}/event.csv"

    event_df = generate_events(NUM_EVENTS, START_DATE, END_DATE, LOCATION_IDS)
    traffic_df = generate_traffic(
        NUM_TRAFFIC,
        event_df,
        START_DATE,
        END_DATE,
        LOCATION_IDS,
        TRAFFIC_PER_EVENT_DATE,
    )

    traffic_df.to_csv(traffic_path, index=False)
    event_df.to_csv(event_path, index=False)

    print(f"Saved {len(traffic_df)} rows to {traffic_path}")
    print(f"Saved {len(event_df)} rows to {event_path}")
    print(f"Traffic rows on same (location, date) as an event: {NUM_EVENTS * TRAFFIC_PER_EVENT_DATE}")
    print("\nTraffic table preview:")
    print(traffic_df.head())
    print("\nEvent table preview:")
    print(event_df.head())
