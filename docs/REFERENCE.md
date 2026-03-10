# 📄 Code reference (modules, functions, parameters)

## 📑 Table of Contents

- [🏗️ Dashboard app (`app.py`)](#️-dashboard-app-apppy)
- [📡 API client (`utils_api.py`)](#-api-client-utils_apipy)
- [🧮 Aggregation & statistics (`utils_data.py`)](#-aggregation--statistics-utils_datapy)
- [🧾 Report builder (`report_builder.py`)](#-report-builder-report_builderpy)
- [🤖 AI client (`utils_ollama.py`)](#-ai-client-utils_ollamapy)
- [🌐 API server (`main.py` + `database.py`)](#-api-server-mainpy--databasepy)
- [🧪 Data generation & loading](#-data-generation--loading)

## 🏗️ Dashboard app (`app.py`)

Purpose: user interface + orchestration (fetch → aggregate → (optional AI) → report).

Key behaviors:
- Fetches traffic + event data once per session.
- User selects:
  - `event_type` (category)
  - `time_window` (e.g. `full day`, `1h before`)
  - `years` (all time or specific years)
- Generates a report into `reports/`.

Notable helpers:
- `_parse_analysis_sections(reply: str) -> dict`: splits AI reply into named sections used by the report.

## 📡 API client (`utils_api.py`)

### `fetch_traffic(api_base, location_id=None, start_date=None, end_date=None, limit=10000) -> pd.DataFrame`

- **Calls**: `GET {API_BASE_URL}/traffic`
- **Filters**:
  - `location_id` (int)
  - `start_date`, `end_date` (YYYY-MM-DD)
- **Returns columns**: `id, location_id, traffic_timestamp, traffic_date, congestion_level`

### `fetch_events(api_base, location_id=None, event_type=None, start_date=None, end_date=None, limit=1000) -> pd.DataFrame`

- **Calls**: `GET {API_BASE_URL}/events`
- **Filters**:
  - `location_id` (int)
  - `event_type` (str)
  - `start_date`, `end_date` (YYYY-MM-DD)
- **Returns columns**: `id, location_id, event_type, event_name, event_date, event_timestamp` (+ `event_duration` when present)

## 🧮 Aggregation & statistics (`utils_data.py`)

Purpose: filter events based on user criteria, match traffic rows to event windows, compute summary statistics and chart payloads.

### `WINDOW_DEFS`

Maps a `time_window` string to a `(start_delta, end_delta)` relative to `event_timestamp`.
- `full day` is a special mode using `(location_id, date)` matching.

### `build_analysis_payload(traffic_df, events_df, years=None, event_types=None, event_name_keywords=None, time_window="full day") -> dict | None`

Returns `None` if nothing matches the chosen criteria. Otherwise returns a payload containing:
- **Overall stats**
  - `avg_congestion_in_window`
  - `baseline_avg`
  - `pct_change_vs_baseline`
  - `n_traffic_rows`, `n_events`
  - `time_window`, `years`
- **Ranking chart inputs**
  - `per_event_type`: list of `{event_type, avg_congestion, n}`
  - `per_event_name`: list of `{event_name, event_type, avg_congestion, n}` (one row per event instance; the report aggregates by name)
- **Time-window breakdown**
  - `time_window_breakdown`: list of `{window, avg_congestion, n}`
- **Significance test**
  - `ttest_pvalue`, `ttest_statistic`: two-sample t-test comparing in-window vs baseline congestion (when both samples have \(n \ge 2\))

## 🧾 Report builder (`report_builder.py`)

Purpose: convert stats + AI text into a single HTML report.

Key functions:
- `_bar_chart_html(df, x_col, y_col, title, color="#DD4633") -> str`: Plotly bar chart; **bar order follows dataframe order**.
- `build_report(...) -> str`: writes an HTML file into `reports/` and returns the file path.

Notes:
- Event impact charts aggregate `per_event_name` into **one bar per event name**.
- The “Time-based impact” section is included **only** when `time_window == "full day"`.

## 🤖 AI client (`utils_ollama.py`)

### `ollama_chat(prompt, api_key, model="gpt-oss:20b-cloud", url="https://ollama.com/api/chat") -> str | None`

- Returns the assistant message content, or `None` if missing key / request fails.

## 🌐 API server (`main.py` + `database.py`)

Purpose: serve data from Supabase to the dashboard.

- `database.py`
  - `get_supabase() -> Client`: singleton Supabase client created from `.env`
- `main.py`
  - `_fetch_all(...)`: paginates to fetch more than 1000 rows
  - `GET /traffic`, `GET /events`: return JSON lists of records

## 🧪 Data generation & loading

- [generate_fake_data.py](../generate_fake_data.py): generates synthetic `traffic.csv` + `event.csv`
- [load_data_to_supabase.py](../load_data_to_supabase.py): loads those CSVs into Supabase tables

