# utils_api.py
# Fetch traffic and event data from the Traffic-Predictor FastAPI
# Used by the Shiny app (app.py)

# 0. Setup #################################

import requests
import pandas as pd
from typing import Optional

# 1. Fetch functions #################################


def fetch_traffic(
    api_base: str,
    location_id: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 10000,
) -> pd.DataFrame:
    """
    GET /traffic from the FastAPI. Returns a DataFrame with columns
    id, location_id, traffic_timestamp, traffic_date, congestion_level.
    """
    url = f"{api_base.rstrip('/')}/traffic"
    params = {"limit": limit}
    if location_id is not None:
        params["location_id"] = location_id
    if start_date is not None:
        params["start_date"] = start_date
    if end_date is not None:
        params["end_date"] = end_date
    r = requests.get(url, params=params, timeout=60)
    r.raise_for_status()
    data = r.json()
    if not data:
        return pd.DataFrame(columns=["id", "location_id", "traffic_timestamp", "traffic_date", "congestion_level"])
    df = pd.DataFrame(data)
    if "traffic_timestamp" in df.columns:
        df["traffic_timestamp"] = pd.to_datetime(df["traffic_timestamp"], errors="coerce")
    if "traffic_date" in df.columns:
        df["traffic_date"] = pd.to_datetime(df["traffic_date"], errors="coerce").dt.date
    return df


def fetch_events(
    api_base: str,
    location_id: Optional[int] = None,
    event_type: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 1000,
) -> pd.DataFrame:
    """
    GET /events from the FastAPI. Returns a DataFrame with columns
    id, location_id, event_type, event_name, event_date, event_timestamp.
    """
    url = f"{api_base.rstrip('/')}/events"
    params = {"limit": limit}
    if location_id is not None:
        params["location_id"] = location_id
    if event_type is not None:
        params["event_type"] = event_type
    if start_date is not None:
        params["start_date"] = start_date
    if end_date is not None:
        params["end_date"] = end_date
    r = requests.get(url, params=params, timeout=60)
    r.raise_for_status()
    data = r.json()
    if not data:
        return pd.DataFrame(
            columns=["id", "location_id", "event_type", "event_name", "event_date", "event_timestamp"]
        )
    df = pd.DataFrame(data)
    if "event_timestamp" in df.columns:
        df["event_timestamp"] = pd.to_datetime(df["event_timestamp"], errors="coerce")
    if "event_date" in df.columns:
        df["event_date"] = pd.to_datetime(df["event_date"], errors="coerce").dt.date
    return df
