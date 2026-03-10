# app.py
# Traffic Predictor Based on Events — Shiny for Python
# Fetches data from FastAPI on load; user selects years, event description, time window; AI report with charts.

# 0. Setup #################################

import os
import re
import json
import time
from pathlib import Path

import pandas as pd
from shiny import App, reactive, render, ui

from utils_api import fetch_traffic, fetch_events
from utils_ollama import ollama_chat
from utils_data import build_analysis_payload
from report_builder import build_report

## 0.1 Load .env ###############################

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

API_BASE_URL = os.environ.get("API_BASE_URL", "http://127.0.0.1:8000")
OLLAMA_API_KEY = os.environ.get("OLLAMA_API_KEY")

# 1. Theme #################################

app_theme = ui.Theme("shiny").add_defaults(primary="#DD4633", body_bg="#FEECEA")

# 2. UI #################################

TIME_WINDOW_CHOICES = [
    "full day",
    "2h before",
    "1h before",
    "during",
    "1hr after",
    "2hr after",
]

# Mockup-aligned UI: no sidebar; one sentence with event type + time window + years, then Generate Report
app_ui = ui.page_fillable(
    ui.h2("Traffic Predictor Based on Events", style="color: #DD4633; margin-top: 0;"),
    ui.card(
        # One sentence: "I would like to understand how [event type] impacts the traffic during [window] of the event."
        ui.div(
            ui.tags.span("I would like to understand how "),
            ui.output_ui("event_type_ui"),
            ui.tags.span(" impacts the traffic during "),
            ui.output_ui("time_window_ui"),
            ui.tags.span(" of the event."),
            style="display: flex; flex-wrap: wrap; align-items: center; gap: 0.35rem; margin-bottom: 1rem;",
        ),
        # Second sentence: "Please analyze based on data of [All time / Specific years]."
        ui.div(
            ui.tags.span("Please analyze based on data of "),
            ui.input_radio_buttons("time_scope", "", ["All time", "Specific years"], selected="All time", inline=True),
            ui.output_ui("years_ui"),
            ui.tags.span("."),
            style="display: flex; flex-wrap: wrap; align-items: center; gap: 0.35rem; margin-bottom: 1rem;",
        ),
        ui.output_ui("estimate_ui"),
        ui.div(
            ui.input_action_button(
                "generate_report",
                "Generate Report",
                class_="btn-primary",
                style="background-color: #DD4633; border: 1px solid #333; color: white;",
            ),
            ui.input_action_button("reset_filter", "Reset filter", class_="btn-outline-secondary ms-2"),
            style="margin-bottom: 0.5rem;",
        ),
        ui.output_ui("report_status_ui"),
        ui.output_ui("report_error_ui"),
        ui.output_ui("report_summary_ui"),
        ui.output_ui("report_download_ui"),
    ),
    ui.card(
        ui.card_header("Data status", style="padding: 0.25rem 0; font-size: 0.95rem;"),
        ui.output_ui("data_status_ui"),
        style="margin-top: auto; padding: 0.5rem 1rem; min-height: 0;",
    ),
    title="Traffic Predictor Based on Events",
    theme=app_theme,
    fillable=True,
)

# 3. Server #################################


def _parse_event_filter_reply(reply: str):
    """Parse Ollama reply into event_types, event_name_keywords, and mode ('category' | 'specific')."""
    if not reply:
        return None, None, None
    reply = reply.strip()
    for pattern in (r"```(?:json)?\s*([\s\S]*?)```", r"\{[\s\S]*\}"):
        m = re.search(pattern, reply)
        if m:
            raw = m.group(1).strip() if "```" in pattern else m.group(0)
            try:
                data = json.loads(raw)
                if isinstance(data, dict):
                    et = data.get("event_types") if isinstance(data.get("event_types"), list) else []
                    kw = data.get("event_name_keywords") if isinstance(data.get("event_name_keywords"), list) else []
                    mode = data.get("mode")
                    if mode not in ("category", "specific"):
                        mode = "category" if et and not kw else ("specific" if kw else "category")
                    return et, kw, mode
            except json.JSONDecodeError:
                pass
    return None, None, None


def _parse_analysis_sections(reply: str):
    """Split AI reply into summary (merged), event_impact_ranking, time_based_impact, suggested_actions."""
    sections = {
        "summary": "",
        "event_impact_ranking": "",
        "time_based_impact": "",
        "suggested_actions": "",
    }
    if not reply:
        return sections
    reply = reply.strip()
    patterns = [
        (r"(?i)(?:##\s*|(?:\*\*)?\s*)(?:Overall\s+summary|Summary)\s*[:\*\n]*([\s\S]*?)(?=##|(?:\*\*)?\s*(?:Event\s+impact|Ranking)|$)", "summary"),
        (r"(?i)(?:##\s*|(?:\*\*)?\s*)(?:Correlation\s+details|Details)\s*[:\*\n]*([\s\S]*?)(?=##|(?:\*\*)?\s*(?:Event\s+impact|Ranking)|$)", "correlation_details"),
        (r"(?i)(?:##\s*|(?:\*\*)?\s*)(?:Event\s+impact\s+ranking|Ranking)\s*[:\*\n]*([\s\S]*?)(?=##|(?:\*\*)?\s*(?:Time-based|Time\s+impact)|$)", "event_impact_ranking"),
        (r"(?i)(?:##\s*|(?:\*\*)?\s*)(?:Time-based\s+impact|Time\s+impact)\s*[:\*\n]*([\s\S]*?)(?=##|(?:\*\*)?\s*(?:Suggested|Actions)|$)", "time_based_impact"),
        (r"(?i)(?:##\s*|(?:\*\*)?\s*)(?:Suggested\s+actions|Actions)\s*[:\*\n]*([\s\S]*?)$", "suggested_actions"),
    ]
    for pattern, key in patterns:
        m = re.search(pattern, reply, re.IGNORECASE | re.DOTALL)
        if m:
            val = m.group(1).strip()
            if key == "correlation_details" and val:
                sections["summary"] = (sections["summary"] + " " + val).strip()
            elif key in sections:
                sections[key] = val
    if not any(sections.values()):
        sections["summary"] = reply
    return sections


def server(input, output, session):
    traffic_df = reactive.Value(None)
    events_df = reactive.Value(None)
    data_load_error = reactive.Value(None)
    report_path = reactive.Value(None)
    report_summary = reactive.Value("")
    report_error = reactive.Value(None)
    report_generating = reactive.Value(False)
    last_run_sec = reactive.Value(None)

    # On session start: fetch traffic and events once
    @reactive.Effect
    def _fetch_data_on_load():
        try:
            t = fetch_traffic(API_BASE_URL, limit=100000)
            e = fetch_events(API_BASE_URL, limit=10000)
            traffic_df.set(t)
            events_df.set(e)
            data_load_error.set(None)
        except Exception as err:
            data_load_error.set(str(err))
            traffic_df.set(None)
            events_df.set(None)

    @reactive.Effect
    @reactive.event(input.reset_filter)
    def _reset_filter():
        report_path.set(None)
        e = events_df.get()
        if e is not None and not e.empty and "event_type" in e.columns:
            types = sorted(e["event_type"].dropna().astype(str).unique().tolist())
            if types:
                ui.update_select("event_type", selected=types[0])
        ui.update_select("time_window", selected="full day")
        ui.update_radio_buttons("time_scope", selected="All time")

    # Event type dropdown (choices from loaded events)
    @output
    @render.ui
    def event_type_ui():
        e = events_df.get()
        if e is None or e.empty or "event_type" not in e.columns:
            choices = ["(loading…)"]
            return ui.input_select("event_type", "", choices=choices, selected=choices[0], width="220px")
        types = sorted(e["event_type"].dropna().astype(str).unique().tolist())
        if not types:
            types = ["(no event types)"]
        return ui.input_select("event_type", "", choices=types, selected=types[0], width="220px")

    # Time window: holiday → only "full day"; other event types → all choices
    # Do not read input.time_window() here—that input is created by this output, so it doesn't exist on first render.
    @output
    @render.ui
    def time_window_ui():
        sel = input.event_type()
        is_holiday = sel and str(sel).strip().lower() == "holiday"
        choices = ["full day"] if is_holiday else TIME_WINDOW_CHOICES
        selected = "full day"
        return ui.input_select("time_window", "", choices=choices, selected=selected)

    # Years: show year checkboxes only when "Specific years" is selected (mutually exclusive with All time)
    @output
    @render.ui
    def years_ui():
        if input.time_scope() != "Specific years":
            return ui.tags.span()
        t = traffic_df.get()
        e = events_df.get()
        years_set = set()
        if t is not None and not t.empty and "traffic_date" in t.columns:
            try:
                tt = pd.to_datetime(t["traffic_date"], errors="coerce")
                years_set.update(tt.dt.year.dropna().astype(int).tolist())
            except Exception:
                pass
        if e is not None and not e.empty and "event_date" in e.columns:
            try:
                ee = pd.to_datetime(e["event_date"], errors="coerce")
                years_set.update(ee.dt.year.dropna().astype(int).tolist())
            except Exception:
                pass
        years = sorted(years_set) if years_set else [2024, 2025]
        choices = [str(y) for y in years]
        return ui.input_checkbox_group("years", "", choices=choices, selected=[choices[0]] if choices else [], inline=True)

    @output
    @render.ui
    def data_status_ui():
        err = data_load_error.get()
        if err is not None:
            return ui.div(
                ui.p("Could not load data. Is the FastAPI running at " + API_BASE_URL + "?", class_="text-danger fw-bold"),
                ui.p(str(err), class_="small text-muted"),
            )
        t = traffic_df.get()
        e = events_df.get()
        if t is not None and e is not None:
            return ui.p(f"Data loaded: {len(t)} traffic records, {len(e)} events.", class_="text-success small mb-0")
        return ui.p("Loading…", class_="text-muted small mb-0")

    @output
    @render.ui
    def report_error_ui():
        err = report_error.get()
        if not err:
            return ui.div()
        return ui.div(ui.p(err, class_="text-danger fw-bold"), class_="p-3")

    @output
    @render.ui
    def estimate_ui():
        """Data-driven estimate or last run time (replaces static ~30 seconds)."""
        sec = last_run_sec.get()
        if sec is not None:
            if sec < 60:
                return ui.p(f"Last report took {int(round(sec))} seconds. Next run: typically 1–3 min.", class_="text-muted small")
            return ui.p(f"Last report took {sec / 60:.1f} min. Next run: typically 1–3 min.", class_="text-muted small")
        t = traffic_df.get()
        e = events_df.get()
        n_t, n_e = (len(t) if t is not None else 0), (len(e) if e is not None else 0)
        # Heuristic: AI analysis dominates (~90–180s), payload is fast after optimization
        est_sec = min(300, max(60, 90 + (n_t / 20000) * 5 + (n_e / 500) * 5))
        est_min = int(round(est_sec / 60))
        return ui.p(f"Estimated time for report: ~{est_min}–{est_min + 1} min (depends on AI service).", class_="text-muted small")

    @output
    @render.ui
    def report_status_ui():
        if report_generating.get():
            sec = last_run_sec.get()
            if sec is not None and sec >= 60:
                return ui.p(f"Generating report… Typically 1–3 min (last run: {sec / 60:.1f} min).", class_="text-muted")
            return ui.p("Generating report… Typically 1–3 min.", class_="text-muted")
        return ui.div()

    @output
    @render.ui
    def report_summary_ui():
        text = report_summary.get() or ""
        if not text.strip():
            return ui.div()
        return ui.div(
            ui.h4("Summary from latest report", class_="mt-3", style="color: #DD4633;"),
            ui.p(text, class_="mb-2"),
            class_="mt-2",
        )

    @output
    @render.ui
    def report_download_ui():
        path = report_path.get()
        if not path:
            return ui.div()
        return ui.div(
            ui.download_button(
                "download_report",
                "Click here to see the full report",
                class_="btn-primary me-2",
            ),
        )

    @output
    @render.download(filename=lambda: Path(report_path.get()).name if report_path.get() else "report.html")
    def download_report():
        path = report_path.get()
        if path and Path(path).exists():
            with open(path, "rb") as f:
                yield f.read()

    @reactive.Effect
    @reactive.event(input.generate_report)
    def _generate_report():
        report_error.set(None)
        report_path.set(None)
        report_summary.set("")
        report_generating.set(True)
        t0 = time.perf_counter()
        try:
            if not OLLAMA_API_KEY:
                report_error.set("Set OLLAMA_API_KEY in .env to generate the AI report.")
                return
            event_type_sel = (input.event_type() or "").strip()
            if not event_type_sel or event_type_sel.startswith("(loading") or event_type_sel.startswith("(no event"):
                report_error.set("Please select an event type from the dropdown.")
                return
            t = traffic_df.get()
            e = events_df.get()
            if t is None or e is None or t.empty or e.empty:
                report_error.set("No data loaded. Ensure the FastAPI is running and try again.")
                return

            time_window = input.time_window() or "full day"
            if input.time_scope() == "All time":
                years = None
            else:
                years_sel = input.years() or []
                years = [int(y) for y in years_sel if str(y).isdigit()]
                if not years:
                    years = None

            # Use selected event type from dropdown (no AI mapping)
            event_types = [event_type_sel]
            event_name_keywords = []
            mode = "category"

            # Filter and aggregate
            payload = build_analysis_payload(
                t, e,
                years=years,
                event_types=event_types,
                event_name_keywords=event_name_keywords if event_name_keywords else None,
                time_window=time_window,
            )
            if payload is None:
                report_error.set(
                    "No data meets the selected criteria: no traffic records fall on the same (location, date) as any selected event. Try different years or another event type."
                )
                return

            # Aggregated event impact rankings (one per event name) so narrative matches charts
            baseline_avg = payload.get("baseline_avg") or 0
            top_by_congestion = ""
            top_by_pct_change = ""
            if payload.get("per_event_name") and baseline_avg:
                pe = pd.DataFrame(payload["per_event_name"])
                agg = pe.groupby("event_name", as_index=False).agg(
                    avg_congestion=("avg_congestion", "mean"),
                    n=("n", "sum"),
                )
                agg["pct_change"] = (agg["avg_congestion"] - baseline_avg) / baseline_avg * 100
                by_cong = agg.sort_values("avg_congestion", ascending=False).head(8)
                by_pct = agg.sort_values("pct_change", ascending=False).head(8)
                top_by_congestion = "Top by average congestion (use this order in Event impact): " + ", ".join(
                    f"{row['event_name']} {row['avg_congestion']:.2f}" for _, row in by_cong.iterrows()
                )
                top_by_pct_change = "Top by % change vs baseline (use this order): " + ", ".join(
                    f"{row['event_name']} {row['pct_change']:+.1f}%" for _, row in by_pct.iterrows()
                )

            # Analysis prompt
            workflow_context = (
                "Traffic-Predictor: Database stores congestion and event data; RestAPI queries it; "
                "Dashboard lets users pick event types; AI analyzes correlation between traffic and events; Output is a report with graphs."
            )
            stats = (
                f"Average congestion in selected window: {payload['avg_congestion_in_window']:.2f}; "
                f"baseline (outside window): {payload['baseline_avg']:.2f}; "
                f"percent change vs baseline: {payload['pct_change_vs_baseline']:.1f}%. "
                f"Traffic rows in window: {payload['n_traffic_rows']}; events: {payload['n_events']}. "
                f"Time window: {payload['time_window']}; years: {payload['years'] or 'all'}."
            )
            if top_by_congestion:
                stats += " " + top_by_congestion + ". " + top_by_pct_change + "."
            if payload.get("per_event_type") and not top_by_congestion:
                stats += " Per event_type: " + json.dumps(payload["per_event_type"][:10])
            if payload.get("per_event_name") and not top_by_congestion:
                stats += " Per event_name (sample): " + json.dumps(payload["per_event_name"][:10])

            event_instruction = (
                "Event impact ranking: Write a reader-friendly 3-5 sentence summary that summarizes the two charts below (average congestion by event and percent change vs baseline). "
                "Use exactly the rankings provided in the statistics above when naming events: the first name in 'Top by average congestion' has the highest congestion; the first in 'Top by % change' has the largest percent increase. "
                "Do not list event names repeatedly or use long dash-style lists. Summarize which events show the highest congestion and the largest percent increase or decrease versus baseline."
            )

            include_time_based = time_window == "full day"
            section_headers = "## Summary, ## Event impact ranking, ## Suggested actions"
            if include_time_based:
                section_headers = "## Summary, ## Event impact ranking, ## Time-based impact, ## Suggested actions"
            section_count = "four sections" if include_time_based else "three sections"
            time_based_instruction = (
                " Time-based impact: Write 3-5 sentences summarizing both time-window charts (average congestion by window and percent change vs baseline). "
                if include_time_based else " "
            )
            analysis_prompt = (
                workflow_context + "\n\nUser asked: how \""
                + event_type_sel
                + "\" impacts traffic during "
                + time_window
                + " of the event. Statistics (averaged across all locations): "
                + stats
                + f"\n\nWrite a short report with exactly these {section_count} (use headers {section_headers}). "
                "Summary: 3-5 sentences total combining overall summary and correlation with baseline (percent increase or decrease). "
                + event_instruction
                + time_based_instruction
                + "Suggested actions: provide either a short paragraph or a bullet list (use - or * at the start of each line for bullets). Do not use ** for emphasis; use plain text only. Be concise and data-driven."
            )
            try:
                analysis_reply = ollama_chat(analysis_prompt, OLLAMA_API_KEY)
            except Exception:
                analysis_reply = None
            parsed = _parse_analysis_sections(analysis_reply or "")
            report_summary.set(parsed.get("summary", ""))

            ttest_note = ""
            pval = payload.get("ttest_pvalue")
            if pval is not None:
                sig = "significant at α = 0.05" if pval < 0.05 else "not significant at α = 0.05"
                ttest_note = f" A two-sample t-test comparing congestion during the event window vs baseline yielded p = {pval:.2f} ({sig})."
            else:
                ttest_note = " Statistical testing was not performed (insufficient data or scipy unavailable)."
            footnotes = (
                "This report uses descriptive statistics (averages, percent change versus baseline) and, when data allow, a two-sample t-test (event-window vs baseline congestion)."
                + ttest_note
                + " Time window applied relative to each event's timestamp (same location_id). Congestion was averaged across all locations. "
                + ("Narrative generated by Ollama from the aggregated statistics." if analysis_reply else "AI narrative was unavailable (timeout or service error); report shows statistics and charts only.")
            )
            criteria = {
                "event_type": event_type_sel,
                "time_window": time_window,
                "years": "All time" if years is None else ", ".join(map(str, years)),
            }
            try:
                t_dates = pd.to_datetime(t["traffic_date"], errors="coerce").dropna()
                traffic_range = f"{t_dates.min().strftime('%Y-%m-%d')} to {t_dates.max().strftime('%Y-%m-%d')}" if len(t_dates) else "—"
            except Exception:
                traffic_range = "—"
            try:
                e_dates = pd.to_datetime(e["event_date"], errors="coerce").dropna()
                event_range = f"{e_dates.min().strftime('%Y-%m-%d')} to {e_dates.max().strftime('%Y-%m-%d')}" if len(e_dates) else "—"
            except Exception:
                event_range = "—"
            dataset_summary = f"Dataset: {len(t)} traffic records and {len(e)} events. Traffic dates: {traffic_range}. Event dates: {event_range}."

            # Step 4: Build report with charts
            path = build_report(
                summary=parsed["summary"],
                event_impact_ranking=parsed["event_impact_ranking"],
                time_based_impact=parsed["time_based_impact"],
                suggested_actions=parsed["suggested_actions"],
                footnotes=footnotes,
                payload=payload,
                criteria=criteria,
                dataset_summary=dataset_summary,
            )
            total_sec = round(time.perf_counter() - t0, 2)
            last_run_sec.set(total_sec)
            report_path.set(path)
        except Exception as exc:
            report_error.set("Report generation failed: " + str(exc))
        finally:
            report_generating.set(False)


app = App(app_ui, server)

# Run on port 8001 by default so FastAPI can use 8000: python app.py
if __name__ == "__main__":
    from shiny import run_app
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8080"))
    run_app(app, host=host, port=port)
