# main.py
# FastAPI app that reads traffic and event data from Supabase
# Pairs with database.py and SUPABASE_SETUP.md

# Uses SUPABASE_URL and SUPABASE_KEY from .env (no DATABASE_URL needed).
# Exposes GET /traffic and GET /events with optional filters.

# 0. Setup #################################

from pathlib import Path
from typing import Optional
from fastapi import FastAPI, Depends, Query
from fastapi.responses import FileResponse, PlainTextResponse
from supabase import Client

from database import get_supabase

_REPORTS_DIR = Path(__file__).resolve().parent / "reports"

# 1. App #################################

app = FastAPI(
    title="Traffic-Predictor API",
    description="Query traffic and event data from Supabase.",
    version="1.0.0",
)


@app.get("/")
def root():
    """Health check and link to docs."""
    return {"message": "Traffic-Predictor API", "docs": "/docs"}


# Supabase returns at most 1000 rows per request by default. Paginate to fetch all.
_PAGE_SIZE = 1000


def _fetch_all(supabase: Client, table: str, select: str, order_col: str, desc: bool = True, **filters) -> list:
    """Paginate through a table and return all rows (works around Supabase 1000-row cap)."""
    date_col = "traffic_date" if table == "traffic" else "event_date"
    q = supabase.table(table).select(select).order(order_col, desc=desc)
    for key, val in filters.items():
        if val is None:
            continue
        if key == "location_id":
            q = q.eq("location_id", val)
        elif key == "event_type":
            q = q.eq("event_type", val)
        elif key == "start_date":
            q = q.gte(date_col, val)
        elif key == "end_date":
            q = q.lte(date_col, val)
    all_rows = []
    offset = 0
    while True:
        page = q.range(offset, offset + _PAGE_SIZE - 1)
        r = page.execute()
        data = r.data or []
        all_rows.extend(data)
        if len(data) < _PAGE_SIZE:
            break
        offset += _PAGE_SIZE
    return all_rows


# 2. Traffic endpoints #################################

@app.get("/traffic")
def get_traffic(
    supabase: Client = Depends(get_supabase),
    location_id: Optional[int] = Query(None, description="Filter by location_id (1–50)"),
    start_date: Optional[str] = Query(None, description="Filter traffic_date >= start_date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="Filter traffic_date <= end_date (YYYY-MM-DD)"),
    limit: int = Query(100, ge=1, le=100000, description="Max rows to return (paginated internally)"),
):
    """
    List traffic records. Optional filters: location_id, start_date, end_date.
    Paginates internally so all requested rows are returned (Supabase caps at 1000/request).
    """
    select = "id, location_id, traffic_timestamp, traffic_date, congestion_level"
    all_data = _fetch_all(
        supabase, "traffic", select, "traffic_timestamp", True,
        location_id=location_id, start_date=start_date, end_date=end_date,
    )
    return all_data[:limit]


# 3. Event endpoints #################################

@app.get("/events")
def get_events(
    supabase: Client = Depends(get_supabase),
    location_id: Optional[int] = Query(None, description="Filter by location_id (1–50)"),
    event_type: Optional[str] = Query(None, description="Filter by event_type (e.g. holiday, weather)"),
    start_date: Optional[str] = Query(None, description="Filter event_date >= start_date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="Filter event_date <= end_date (YYYY-MM-DD)"),
    limit: int = Query(100, ge=1, le=10000, description="Max rows to return (paginated internally)"),
):
    """
    List event records. Optional filters: location_id, event_type, start_date, end_date.
    Paginates internally so all requested rows are returned (Supabase caps at 1000/request).
    """
    select = "id, location_id, event_type, event_name, event_date, event_timestamp, event_duration"
    all_data = _fetch_all(
        supabase, "event", select, "event_timestamp", True,
        location_id=location_id, event_type=event_type, start_date=start_date, end_date=end_date,
    )
    return all_data[:limit]


# 4. Serve generated reports (for Shiny dashboard "Open report") #################################

@app.get("/reports/{filename:path}")
def get_report(filename: str):
    """Serve a generated report HTML file from the reports/ directory. Safe path resolution only under reports/."""
    if not filename or ".." in filename or filename.startswith("/"):
        return PlainTextResponse("Invalid path", status_code=400)
    path = (_REPORTS_DIR / filename).resolve()
    reports_resolved = _REPORTS_DIR.resolve()
    if not path.is_file() or reports_resolved not in path.parents:
        return PlainTextResponse("Not found", status_code=404)
    return FileResponse(path, media_type="text/html")


# 5. Run with: uvicorn main:app --reload #################################
