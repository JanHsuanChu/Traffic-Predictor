# 📄 Codebook (data dictionary)

## 📑 Table of Contents

- [📊 Overview](#-overview)
- [🗃️ `traffic.csv` / `traffic` table](#️-trafficcsv--traffic-table)
- [🗃️ `event.csv` / `event` table](#️-eventcsv--event-table)
- [🧾 Notes on joins & time windows](#-notes-on-joins--time-windows)
- [🔗 Related files](#-related-files)

## 📊 Overview

The dashboard and report use two datasets:
- `traffic` (congestion measurements)
- `event` (events that may affect traffic)

You can provide data as CSVs (`traffic.csv`, `event.csv`) and load them to Supabase, or directly populate the tables in Supabase.

## 🗃️ `traffic.csv` / `traffic` table

Primary purpose: represent congestion for a location at a point in time.

| field | type | example | meaning |
|---|---|---|---|
| `location_id` | int | `12` | location identifier used to join with `event.location_id` |
| `traffic_timestamp` | datetime / timestamptz | `2024-06-01 08:15:00+00:00` | timestamp of the traffic measurement |
| `traffic_date` | date | `2024-06-01` | date portion used for “full day” matching |
| `congestion_level` | int (1–10) | `7` | congestion scale (1 = low, 10 = high) |

Optional/system field (when loaded into Postgres):
- `id`: bigint primary key

## 🗃️ `event.csv` / `event` table

Primary purpose: represent an event occurring at a location and time.

| field | type | example | meaning |
|---|---|---|---|
| `location_id` | int | `12` | location identifier used to join with traffic |
| `event_type` | text | `Sport & cultural` | category used by the dashboard filter |
| `event_name` | text | `Jazz festival downtown` | specific event label (used for event-name aggregation in the report) |
| `event_date` | date | `2024-06-01` | date portion used for “full day” matching |
| `event_timestamp` | datetime / timestamptz | `2024-06-01 09:00:00+00:00` | anchor timestamp for time-window matching |
| `event_duration` | int (minutes) | `120` | duration of the event (default 60) |

Optional/system field (when loaded into Postgres):
- `id`: bigint primary key

## 🧾 Notes on joins & time windows

- **Join key**: `location_id`
- **Full day mode**: traffic is matched to an event if it shares the same `(location_id, traffic_date == event_date)`.
- **Timed windows** (e.g. `1h before`, `during`): traffic is matched if `traffic_timestamp` falls in the selected window relative to `event_timestamp`.
- **Baseline**: traffic rows that do not fall into any matched event window under the chosen criteria.

## 🔗 Related files

- [supabase_migration_traffic_event.sql](../supabase_migration_traffic_event.sql): table definitions
- [utils_data.py](../utils_data.py): matching + aggregation logic used in reports
- [generate_fake_data.py](../generate_fake_data.py): synthetic data generator (shapes match this codebook)

