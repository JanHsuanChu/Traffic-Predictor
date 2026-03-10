# 📄 Traffic-Predictor API (FastAPI)

## 📑 Table of Contents

- [📊 Overview](#-overview)
- [▶️ Run the API](#️-run-the-api)
- [🔑 Authentication](#-authentication)
- [🧾 Endpoints](#-endpoints)
- [🧪 Example requests](#-example-requests)
- [🔗 Related files](#-related-files)

## 📊 Overview

The API is a thin wrapper over Supabase tables:
- `traffic`
- `event`

It paginates internally to work around the default Supabase 1000-row cap, then returns up to the caller’s requested `limit`.

## ▶️ Run the API

```bash
cd Traffic-Predictor
uvicorn main:app --reload
```

Open interactive docs at `http://127.0.0.1:8000/docs`.

## 🔑 Authentication

The API server reads Supabase credentials from `Traffic-Predictor/.env`:
- `SUPABASE_URL`
- `SUPABASE_KEY` (or the fallback `SUPABSE_SERVICE_ROLE_KEY` if present)

The API itself does not implement user auth; it assumes you run it locally for development.

## 🧾 Endpoints

### `GET /`

- **Purpose**: health check
- **Returns**: a JSON object containing `docs` path

### `GET /traffic`

- **Purpose**: fetch traffic records from Supabase
- **Query params**
  - `location_id` (int, optional)
  - `start_date` (str `YYYY-MM-DD`, optional) — filters `traffic_date >= start_date`
  - `end_date` (str `YYYY-MM-DD`, optional) — filters `traffic_date <= end_date`
  - `limit` (int, default 100, max 100000)
- **Returns**: list of rows with fields:
  - `id`, `location_id`, `traffic_timestamp`, `traffic_date`, `congestion_level`

### `GET /events`

- **Purpose**: fetch event records from Supabase
- **Query params**
  - `location_id` (int, optional)
  - `event_type` (str, optional)
  - `start_date` (str `YYYY-MM-DD`, optional) — filters `event_date >= start_date`
  - `end_date` (str `YYYY-MM-DD`, optional) — filters `event_date <= end_date`
  - `limit` (int, default 100, max 10000)
- **Returns**: list of rows with fields:
  - `id`, `location_id`, `event_type`, `event_name`, `event_date`, `event_timestamp`, `event_duration`

### `GET /reports/{filename}`

- **Purpose**: serve generated HTML reports from `Traffic-Predictor/reports/`
- **Notes**: path traversal is blocked (`..` rejected)

## 🧪 Example requests

```bash
curl "http://127.0.0.1:8000/traffic?limit=5"
curl "http://127.0.0.1:8000/events?event_type=Sport%20%26%20cultural&limit=5"
```

## 🔗 Related files

- [main.py](../main.py): FastAPI app + pagination logic
- [database.py](../database.py): Supabase client initialization
- [SUPABASE_SETUP.md](../SUPABASE_SETUP.md): Supabase setup and migration steps

