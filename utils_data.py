# utils_data.py
# Filter and aggregate traffic and event data for the Shiny app report
# Accepts AI-resolved event filter; applies time window; returns payload for analysis and charts

# 0. Setup #################################

import pandas as pd
from datetime import timedelta
from typing import Any, Optional

try:
    from scipy import stats as scipy_stats
except ImportError:
    scipy_stats = None

# 1. Time window definitions #################################

# Each window is (start_delta, end_delta) relative to event_timestamp.
# None for "full day" means use event_date only.
WINDOW_DEFS = {
    "full day": None,  # traffic_date == event_date
    "2h before": (timedelta(hours=-2), timedelta(0)),
    "1h before": (timedelta(hours=-1), timedelta(0)),
    "during": (timedelta(minutes=-30), timedelta(minutes=30)),
    "1hr after": (timedelta(0), timedelta(hours=1)),
    "2hr after": (timedelta(0), timedelta(hours=2)),
}


def _filter_events(
    events_df: pd.DataFrame,
    years: Optional[list[int]] = None,
    event_types: Optional[list[str]] = None,
    event_name_keywords: Optional[list[str]] = None,
) -> pd.DataFrame:
    """Filter events by selected years and AI-resolved event_type / event_name keywords."""
    if events_df is None or events_df.empty:
        return pd.DataFrame()
    df = events_df.copy()
    if "event_date" in df.columns and df["event_date"].dtype == object:
        df["event_date"] = pd.to_datetime(df["event_date"], errors="coerce")
    if years is not None and len(years) > 0:
        df["_year"] = pd.to_datetime(df["event_date"]).dt.year
        df = df[df["_year"].isin(years)].drop(columns=["_year"], errors="ignore")
    if event_types is not None and len(event_types) > 0:
        col = df["event_type"].astype(str).str.strip()
        col_lower = col.str.lower()
        wanted_lower = [s.strip().lower() for s in event_types if s and str(s).strip()]
        # Exact match (case-insensitive) or event_type contains any requested phrase/word
        mask = col_lower.isin(wanted_lower)
        for w in wanted_lower:
            if w:
                mask = mask | col_lower.str.contains(w, regex=False, na=False)
                # Also match by first word (e.g. "sport" matches "Sport & cultural" or "Sport and cultural")
                parts = [p for p in w.replace("&", " ").split() if len(p) >= 2]
                for part in parts:
                    mask = mask | col_lower.str.contains(part, regex=False, na=False)
        df = df[mask]
    if event_name_keywords is not None and len(event_name_keywords) > 0:
        name_lower = df["event_name"].fillna("").astype(str).str.lower()
        mask = name_lower.str.contains("|".join(kw.strip().lower() for kw in event_name_keywords if kw.strip()), regex=True, na=False)
        df = df[mask]
    return df.reset_index(drop=True)


def _traffic_in_window(
    traffic_row_ts: pd.Timestamp,
    traffic_loc: int,
    event_ts: pd.Timestamp,
    event_loc: int,
    window_key: str,
) -> bool:
    """True if this traffic row falls in the chosen time window for this event (same location)."""
    if traffic_loc != event_loc:
        return False
    window = WINDOW_DEFS.get(window_key)
    if window is None:
        return True
    start_d, end_d = window
    lo = event_ts + start_d
    hi = event_ts + end_d
    return lo <= traffic_row_ts < hi


def _to_date_str(val) -> str:
    """Normalize to YYYY-MM-DD string for reliable comparison."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return ""
    if hasattr(val, "isoformat"):
        return val.isoformat()[:10] if hasattr(val, "isoformat") else str(val)[:10]
    s = str(val).strip()[:10]
    return s if len(s) == 10 else ""


def _traffic_full_day(traffic_date, event_date) -> bool:
    """True if traffic_date and event_date are the same calendar day (for full-day window)."""
    if traffic_date is None or event_date is None:
        return False
    if hasattr(event_date, "date"):
        event_date = event_date.date()
    return _to_date_str(traffic_date) == _to_date_str(event_date) and _to_date_str(traffic_date) != ""


def build_analysis_payload(
    traffic_df: pd.DataFrame,
    events_df: pd.DataFrame,
    years: Optional[list[int]] = None,
    event_types: Optional[list[str]] = None,
    event_name_keywords: Optional[list[str]] = None,
    time_window: str = "1h before",
) -> Optional[dict[str, Any]]:
    """
    Filter events by years and event filter; match traffic to events by location and time window;
    aggregate congestion. Returns a payload dict for the AI prompt and report charts, or None if no data.
    """
    if traffic_df is None or traffic_df.empty or events_df is None or events_df.empty:
        return None

    events_f = _filter_events(events_df, years=years, event_types=event_types, event_name_keywords=event_name_keywords)
    if events_f.empty:
        return None

    # Ensure timestamps
    if "traffic_timestamp" in traffic_df.columns:
        traffic_df = traffic_df.copy()
        traffic_df["traffic_timestamp"] = pd.to_datetime(traffic_df["traffic_timestamp"], errors="coerce")
        traffic_df = traffic_df.dropna(subset=["traffic_timestamp"])
    if "event_timestamp" not in events_f.columns:
        return None
    events_f = events_f.copy()
    events_f["event_timestamp"] = pd.to_datetime(events_f["event_timestamp"], errors="coerce")
    events_f = events_f.dropna(subset=["event_timestamp"])

    window = WINDOW_DEFS.get(time_window, WINDOW_DEFS["1h before"])
    is_full_day = window is None

    matched_traffic_idxs = set()

    if is_full_day:
        # Full day: traffic on same (location_id, date) as any event. Use set for reliable matching.
        event_loc_dates = set()
        for _, ev in events_f.iterrows():
            loc = ev.get("location_id")
            ed = ev.get("event_date") or ev.get("event_timestamp")
            if hasattr(ed, "date"):
                ed = ed.date()
            edate_str = _to_date_str(ed)
            if loc is not None and edate_str:
                event_loc_dates.add((int(loc), edate_str))
        for idx, row in traffic_df.iterrows():
            loc = row.get("location_id")
            tdate = row.get("traffic_date")
            if tdate is None and "traffic_timestamp" in row:
                ts = row["traffic_timestamp"]
                tdate = ts.date() if hasattr(ts, "date") else ts
            tdate_str = _to_date_str(tdate)
            try:
                loc_int = int(loc) if loc is not None else None
            except (TypeError, ValueError):
                loc_int = None
            if loc_int is not None and tdate_str and (loc_int, tdate_str) in event_loc_dates:
                matched_traffic_idxs.add(idx)
    else:
        for _, ev in events_f.iterrows():
            loc = ev["location_id"]
            ets = ev["event_timestamp"]
            start_d, end_d = window
            lo, hi = ets + start_d, ets + end_d
            for idx, row in traffic_df.iterrows():
                if row["location_id"] != loc:
                    continue
                ts = row["traffic_timestamp"]
                if lo <= ts < hi:
                    matched_traffic_idxs.add(idx)

    if not matched_traffic_idxs:
        return None

    traffic_in = traffic_df.loc[list(matched_traffic_idxs)]
    avg_in_window = float(traffic_in["congestion_level"].mean())
    baseline_df = traffic_df[~traffic_df.index.isin(matched_traffic_idxs)]
    baseline_avg = float(baseline_df["congestion_level"].mean()) if len(baseline_df) > 0 else avg_in_window
    pct_change = ((avg_in_window - baseline_avg) / baseline_avg * 100) if baseline_avg else 0.0

    ttest_pvalue: Optional[float] = None
    ttest_statistic: Optional[float] = None
    if scipy_stats is not None and len(traffic_in) >= 2 and len(baseline_df) >= 2:
        try:
            in_vals = traffic_in["congestion_level"].astype(float)
            base_vals = baseline_df["congestion_level"].astype(float)
            res = scipy_stats.ttest_ind(in_vals, base_vals, nan_policy="omit")
            if res is not None and hasattr(res, "statistic") and hasattr(res, "pvalue"):
                ttest_statistic = float(res.statistic)
                ttest_pvalue = float(res.pvalue)
        except Exception:
            pass

    # Index matched traffic by (loc, date) and by loc+ts for fast lookups (avoid O(events*traffic) loops)
    loc_date_to_cong = {}  # (loc, date_str) -> list of congestion_level (for full-day path)
    traffic_by_loc = {}  # loc -> list of (idx, ts, congestion_level) (for timed path and breakdown)
    for idx in matched_traffic_idxs:
        row = traffic_df.loc[idx]
        loc = row.get("location_id")
        if loc is None:
            continue
        try:
            loc_int = int(loc)
        except (TypeError, ValueError):
            continue
        ts = row["traffic_timestamp"]
        cong = float(row["congestion_level"])
        traffic_by_loc.setdefault(loc_int, []).append((idx, ts, cong))
        tdate = row.get("traffic_date")
        if tdate is None and "traffic_timestamp" in row:
            tdate = ts.date() if hasattr(ts, "date") else ts
        tdate_str = _to_date_str(tdate)
        if tdate_str:
            loc_date_to_cong.setdefault((loc_int, tdate_str), []).append(cong)

    # Per-event-type aggregate (for ranking chart) — use indexes, no full traffic scan
    event_type_avgs = []
    for etype in events_f["event_type"].unique():
        sub_events = events_f[events_f["event_type"] == etype]
        congs, n = [], 0
        if is_full_day:
            for _, ev in sub_events.iterrows():
                loc = ev.get("location_id")
                ed = ev.get("event_date") or ev.get("event_timestamp")
                if hasattr(ed, "date"):
                    ed = ed.date()
                edate_str = _to_date_str(ed)
                if loc is None or not edate_str:
                    continue
                try:
                    key = (int(loc), edate_str)
                except (TypeError, ValueError):
                    continue
                for c in loc_date_to_cong.get(key, []):
                    congs.append(c)
                    n += 1
        else:
            start_d, end_d = window
            seen_idx = set()
            for _, ev in sub_events.iterrows():
                loc = ev["location_id"]
                try:
                    loc_int = int(loc)
                except (TypeError, ValueError):
                    continue
                ets = ev["event_timestamp"]
                lo, hi = ets + start_d, ets + end_d
                for (idx, ts, c) in traffic_by_loc.get(loc_int, []):
                    if idx not in seen_idx and lo <= ts < hi:
                        seen_idx.add(idx)
                        congs.append(c)
                        n += 1
        if congs:
            event_type_avgs.append({"event_type": etype, "avg_congestion": sum(congs) / len(congs), "n": len(congs)})

    # Per-event-name aggregate (top N for ranking) — use indexes
    event_name_avgs = []
    for _, ev in events_f.iterrows():
        ename = ev["event_name"]
        loc = ev["location_id"]
        ets = ev["event_timestamp"]
        edate = ev["event_date"]
        congs = []
        if is_full_day:
            if hasattr(edate, "date"):
                edate = edate.date()
            edate_str = _to_date_str(edate or ets)
            try:
                key = (int(loc), edate_str)
            except (TypeError, ValueError):
                continue
            congs = loc_date_to_cong.get(key, [])
        else:
            start_d, end_d = window
            lo, hi = ets + start_d, ets + end_d
            try:
                loc_int = int(loc)
            except (TypeError, ValueError):
                continue
            for (_, ts, c) in traffic_by_loc.get(loc_int, []):
                if lo <= ts < hi:
                    congs.append(c)
        if congs:
            event_name_avgs.append({
                "event_name": ename,
                "event_type": ev["event_type"],
                "avg_congestion": sum(congs) / len(congs),
                "n": len(congs),
            })

    # Time-based breakdown: compute avg congestion for each window type (for chart) — use indexes
    time_window_avgs = []
    for wkey in WINDOW_DEFS:
        w = WINDOW_DEFS[wkey]
        congs = []
        if w is None:
            for key, vals in loc_date_to_cong.items():
                congs.extend(vals)
        else:
            start_d, end_d = w
            seen_idx = set()
            for _, ev in events_f.iterrows():
                loc = ev["location_id"]
                try:
                    loc_int = int(loc)
                except (TypeError, ValueError):
                    continue
                ets = ev["event_timestamp"]
                lo, hi = ets + start_d, ets + end_d
                for (idx, ts, c) in traffic_by_loc.get(loc_int, []):
                    if idx not in seen_idx and lo <= ts < hi:
                        seen_idx.add(idx)
                        congs.append(c)
        if congs:
            time_window_avgs.append({
                "window": wkey,
                "avg_congestion": sum(congs) / len(congs),
                "n": len(congs),
            })

    return {
        "avg_congestion_in_window": avg_in_window,
        "baseline_avg": baseline_avg,
        "pct_change_vs_baseline": pct_change,
        "n_traffic_rows": len(matched_traffic_idxs),
        "n_events": len(events_f),
        "time_window": time_window,
        "years": years,
        "event_types": event_types or [],
        "event_name_keywords": event_name_keywords or [],
        "per_event_type": event_type_avgs,
        "per_event_name": event_name_avgs,
        "time_window_breakdown": time_window_avgs,
        "ttest_pvalue": ttest_pvalue,
        "ttest_statistic": ttest_statistic,
    }
