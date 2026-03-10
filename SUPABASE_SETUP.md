# Supabase setup for Traffic-Predictor

This guide walks you through hosting the **traffic** and **event** tables on your Supabase project.

**Project URL:** `https://stnfxxjktzznvlfhczcz.supabase.co`  
**Project reference (for MCP):** `stnfxxjktzznvlfhczcz`

---

## What you need

1. **Supabase project** — You already have one at the URL above.
2. **API key** — From the Supabase Dashboard (anon key is enough for inserting from a script if Row Level Security allows it; otherwise use the service_role key for back-end scripts only).
3. **Tables** — Create `traffic` and `event` with the SQL below.
4. **Data** — Load the CSV data via the Dashboard or the provided Python script.

---

## Step 1: Get your API key

1. Open [Supabase Dashboard](https://supabase.com/dashboard) and select your project.
2. Go to **Project Settings** (gear icon) → **API**.
3. Copy:
   - **Project URL** (e.g. `https://stnfxxjktzznvlfhczcz.supabase.co`)
   - **anon public** key (for client-side or scripts; keep it out of public repos)

For the Python load script, the **service_role** key is more convenient (bypasses RLS). Use it only in a secure environment and never in front-end code.

---

## Step 2: Create the tables

**If Supabase MCP is connected in Cursor:** Ask the AI to "apply the migration in `supabase_migration_traffic_event.sql`" or "execute the SQL in that file." You can also verify MCP by asking: "What tables are in my Supabase database? Use MCP tools."

You can otherwise create the tables as follows.

### Option A: Supabase Dashboard (SQL Editor)

1. In the Dashboard, open **SQL Editor**.
2. Paste the contents of `supabase_migration_traffic_event.sql` (in this folder).
3. Click **Run**.  
   This creates the `traffic` and `event` tables.

### Option B: Supabase MCP (if configured in Cursor)

1. [Configure the Supabase MCP](https://supabase.com/docs/guides/getting-started/mcp) in Cursor: **Settings → Cursor Settings → Tools & MCP**.
2. Add the Supabase MCP server with your project ref:  
   `https://mcp.supabase.com/mcp?project_ref=stnfxxjktzznvlfhczcz`
3. After connecting, you can ask the AI to “apply the migration in `supabase_migration_traffic_event.sql`” or to “run the SQL that creates the traffic and event tables.”
4. The MCP tool `apply_migration` or `execute_sql` can run the same SQL.

---

## Step 3: Load the CSV data

### Option A: Python script (recommended)

1. Install dependencies (from the `Traffic-Predictor` folder):
   ```bash
   pip install -r requirements.txt
   ```
   Or: `pip install supabase pandas`
2. Set your project URL and key (use **service_role** if you want to bypass RLS for loading):
   ```bash
   export SUPABASE_URL="https://stnfxxjktzznvlfhczcz.supabase.co"
   export SUPABASE_KEY="your-service_role-or-anon-key"
   ```
   Or create a `.env` file in `Traffic-Predictor` and source it (do not commit the key):
   ```bash
   # .env (do not commit)
   SUPABASE_URL=https://stnfxxjktzznvlfhczcz.supabase.co
   SUPABASE_KEY=your-key-here
   ```
   Then: `export $(grep -v '^#' .env | xargs)` (or use your shell’s way of loading `.env`).
3. From the `Traffic-Predictor` folder, run:
   ```bash
   python load_data_to_supabase.py
   ```
   The script reads `traffic.csv` and `event.csv` and inserts rows into the `traffic` and `event` tables.

### Option B: Dashboard Table Editor

1. In the Dashboard, open **Table Editor**.
2. Select the **traffic** table → **Insert** → **Import data from CSV** and upload `traffic.csv`.
3. Repeat for the **event** table with `event.csv`.  
   Ensure column names and types match (the script and SQL use `location_id`, timestamps, and dates as in the CSVs).

---

## Step 4: Verify

- In **Table Editor**, open `traffic` and `event` and confirm row counts (e.g. 10,000 and 100).
- Or run in SQL Editor:
  ```sql
  SELECT 'traffic' AS table_name, COUNT(*) AS n FROM traffic
  UNION ALL
  SELECT 'event', COUNT(*) FROM event;
  ```

---

## FastAPI (optional)

A FastAPI app in `main.py` queries traffic and events via the **Supabase REST API**, using the same **SUPABASE_URL** and **SUPABASE_KEY** (or **SUPABSE_SERVICE_ROLE_KEY**) as the loader. **No DATABASE_URL or database password is required.**

1. **Install and run** (from the `Traffic-Predictor` folder, with `.env` already containing your Supabase URL and key):
   ```bash
   pip install -r requirements.txt
   uvicorn main:app --reload
   ```
2. Open http://127.0.0.1:8000/docs for the interactive API docs. Endpoints: `GET /traffic`, `GET /events` (with optional filters).

---

## Summary

| Step | Action |
|------|--------|
| 1 | Get **Project URL** and **anon** (or **service_role**) key from Dashboard → Settings → API. |
| 2 | Create tables: run `supabase_migration_traffic_event.sql` in SQL Editor or via MCP. |
| 3 | Load data: run `load_data_to_supabase.py` (with `SUPABASE_URL` and `SUPABASE_KEY` set) or import CSVs in Table Editor. |
| 4 | Check row counts in Table Editor or with the SQL above. |
| 5 | (Optional) Run `uvicorn main:app --reload` for the FastAPI (uses same `.env` as step 3). |

For more on Supabase MCP (list tables, run SQL, apply migrations), see [Supabase MCP – Getting started](https://supabase.com/docs/guides/getting-started/mcp).

---

## Troubleshooting

- **Permission denied when inserting:** If Row Level Security (RLS) is enabled on the tables, either use the **service_role** key for the load script (it bypasses RLS) or add policies that allow insert. The migration file does not enable RLS by default.
- **MCP not listing your project:** In Cursor, add the MCP with `project_ref=stnfxxjktzznvlfhczcz` and complete the browser login to grant access.
