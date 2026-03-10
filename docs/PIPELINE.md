# 📄 Data pipeline & reproducibility

## 📑 Table of Contents

- [🎯 Goal](#-goal)
- [🧱 Data sources](#-data-sources)
- [🔄 Pipeline steps](#-pipeline-steps)
- [▶️ Reproduce end-to-end](#️-reproduce-end-to-end)
- [🧾 Outputs](#-outputs)
- [🔗 Related files](#-related-files)

## 🎯 Goal

Provide a reproducible path to:
1) create or obtain traffic + event data,  
2) load it into Supabase,  
3) run the API + dashboard,  
4) generate an HTML report.

## 🧱 Data sources

This repo supports two data paths:

- **Synthetic data (fully reproducible)**: generated locally into CSVs.
- **Supabase tables**: populated by loading those CSVs (or your own compatible CSVs).

Variable definitions for CSVs live in: [CODEBOOK.md](./CODEBOOK.md)

## 🔄 Pipeline steps

### 1) Generate CSVs (synthetic)

Script: [generate_fake_data.py](../generate_fake_data.py)

- Writes:
  - `traffic.csv` (default 50,000 rows)
  - `event.csv` (default 1,000 rows)
- Date range: Jan 2024 – Dec 2025
- Locations: `location_id` in 1–50
- Design choice: many traffic rows share the same `(location_id, date)` as events so matches exist for analysis.

### 2) Create tables in Supabase

SQL migrations:
- [supabase_migration_traffic_event.sql](../supabase_migration_traffic_event.sql)
- [supabase_migration_add_event_duration.sql](../supabase_migration_add_event_duration.sql)

### 3) Load CSVs into Supabase

Script: [load_data_to_supabase.py](../load_data_to_supabase.py)

- Reads: `traffic.csv`, `event.csv`
- Inserts into: Supabase `traffic`, `event` tables in batches (default batch size = 500)
- Requires `SUPABASE_URL` and `SUPABASE_KEY` in `Traffic-Predictor/.env`

### 4) Serve data via FastAPI

App: [main.py](../main.py)

- Provides `GET /traffic` and `GET /events` used by the dashboard.

### 5) Analyze + report via Shiny dashboard

Dashboard: [app.py](../app.py)

- Fetches data from the API
- Aggregates and computes statistics: [utils_data.py](../utils_data.py)
- (Optional) gets an AI narrative: [utils_ollama.py](../utils_ollama.py)
- Builds the final HTML: [report_builder.py](../report_builder.py)

## ▶️ Reproduce end-to-end

```bash
cd Traffic-Predictor
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 1) Generate synthetic data
python generate_fake_data.py

# 2) Apply migrations in Supabase (see SUPABASE_SETUP.md), then load data
python load_data_to_supabase.py

# 3) Run the API (terminal 1)
uvicorn main:app --reload

# 4) Run the dashboard (terminal 2)
python app.py
```

Then open `http://127.0.0.1:8001` and click **Generate Report**.

## 🧾 Outputs

- **Reports**: `Traffic-Predictor/reports/traffic_report_YYYYMMDD_HHMMSS.html`
- **Generated CSVs** (synthetic path): `traffic.csv`, `event.csv`

## 🔗 Related files

- [SUPABASE_SETUP.md](../SUPABASE_SETUP.md): Supabase setup and loading walkthrough
- [CODEBOOK.md](./CODEBOOK.md): data dictionary for CSVs / tables

