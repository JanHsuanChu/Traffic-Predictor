# report_builder.py
# Builds the Traffic-Predictor HTML report with AI sections and Plotly charts
# Used by app.py when the user clicks Generate Report

# 0. Setup #################################

from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

_REPORTS_DIR = Path(__file__).resolve().parent / "reports"

_REPORT_CSS = """
    body { font-family: Arial, sans-serif; max-width: 980px; margin: 40px auto; padding: 20px; background-color: #FEECEA; color: #333; }
    h1 { color: #DD4633; border-bottom: 3px solid #DD4633; padding-bottom: 10px; }
    h2 { color: #DD4633; margin-top: 28px; border-bottom: 2px solid #DD4633; padding-bottom: 5px; }
    h3 { color: #DD4633; margin-top: 20px; }
    hr { border: 2px solid #DD4633; margin: 30px 0; }
    table { border-collapse: collapse; width: 100%; margin: 15px 0; background-color: white; }
    th, td { border: 1px solid #ddd; padding: 8px 12px; }
    th { background-color: #DD4633; color: white; text-align: left; font-weight: bold; }
    tr:nth-child(even) { background-color: #f9f9f9; }
    small { font-size: 0.85em; color: #666; display: block; margin-top: 10px; }
    .appendix { color: #555; font-size: 0.9em; }
    .appendix table { font-size: 0.9em; }
    .appendix h2, .appendix h3 { color: #555; border-bottom-color: #999; }
"""


def _ensure_reports_dir():
    _REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def _strip_double_asterisks(text: str) -> str:
    """Remove ** from AI-generated text so it renders as plain text in HTML."""
    if not text:
        return text
    return str(text).replace("**", "")


def _format_suggested_actions(text: str) -> str:
    """Format as paragraph or bullet list for reader-friendly display."""
    if not text or not text.strip():
        return "<p>—</p>"
    text = text.strip()
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    bullet_starts = ("-", "*", "•", "·")
    if lines and any(ln.startswith(bullet_starts) for ln in lines):
        items = []
        for ln in lines:
            for b in bullet_starts:
                if ln.startswith(b):
                    ln = ln[1:].strip()
                    break
            if ln:
                items.append(f"<li>{ln}</li>")
        if items:
            return "<ul>" + "".join(items) + "</ul>"
    return f"<p>{text}</p>"


def _bar_chart_html(df: pd.DataFrame, x_col: str, y_col: str, title: str, color: str = "#DD4633") -> str:
    """Plotly bar chart to HTML fragment. Bar order follows dataframe row order (e.g. descending)."""
    if df is None or df.empty:
        fig = go.Figure().add_annotation(text="No data", showarrow=False)
    else:
        fig = px.bar(df, x=x_col, y=y_col, title=title)
        fig.update_traces(marker_color=color)
        fig.update_layout(
            margin=dict(t=40, b=60, l=60, r=40),
            xaxis_tickangle=-45,
            xaxis={"categoryorder": "array", "categoryarray": df[x_col].astype(str).tolist()},
        )
    return fig.to_html(full_html=False, include_plotlyjs="cdn")


def build_report(
    summary: str,
    event_impact_ranking: str,
    time_based_impact: str,
    suggested_actions: str,
    footnotes: str,
    payload: Optional[dict[str, Any]] = None,
    criteria: Optional[dict[str, Any]] = None,
    dataset_summary: Optional[str] = None,
    title: str = "Traffic Predictor Report",
    correlation_details: Optional[str] = None,
) -> str:
    """
    Build HTML report with Summary, Event impact, Time-based impact, Suggested actions, and appendix.
    Writes to reports/traffic_report_YYYYMMDD_HHMMSS.html and returns the file path.
    """
    _ensure_reports_dir()
    now = datetime.now()
    filename = f"traffic_report_{now.strftime('%Y%m%d_%H%M%S')}.html"
    out_path = _REPORTS_DIR / filename

    summary_clean = _strip_double_asterisks(summary or "")
    event_impact_clean = _strip_double_asterisks(event_impact_ranking or "")
    time_based_clean = _strip_double_asterisks(time_based_impact or "")
    suggested_clean = _strip_double_asterisks(suggested_actions or "")

    parts = []
    parts.append(f"<h1>{title}</h1>")
    parts.append(f"<p><em>Generated: {now.strftime('%Y-%m-%d %H:%M')} (local time)</em></p>")
    if criteria:
        parts.append("<p><strong>Criteria:</strong> ")
        parts.append(f"Event type: {criteria.get('event_type', '—')} | ")
        parts.append(f"Time window: {criteria.get('time_window', '—')} | ")
        parts.append(f"Data: {criteria.get('years', '—')}</p>")
    parts.append("<hr />")

    parts.append("<h2>Summary</h2>")
    parts.append(f"<p>{summary_clean or '—'}</p>")
    parts.append("<hr />")

    # Event impact ranking: summary text first, then two charts (aggregate by event name, sort descending)
    parts.append("<h2>Event impact ranking</h2>")
    parts.append(f"<p>{event_impact_clean or '—'}</p>")
    if payload and (payload.get("per_event_type") or payload.get("per_event_name")):
        baseline = payload.get("baseline_avg") or 0
        name_col = "event_name"
        if payload.get("per_event_name"):
            chart_df = pd.DataFrame(payload["per_event_name"])
            chart_df = chart_df.groupby("event_name", as_index=False).agg(
                avg_congestion=("avg_congestion", "mean"),
                n=("n", "sum"),
            )
        else:
            chart_df = pd.DataFrame(payload["per_event_type"])
            name_col = "event_type"
        if baseline and not chart_df.empty:
            chart_df = chart_df.copy()
            chart_df["pct_change"] = (chart_df["avg_congestion"] - baseline) / baseline * 100
        if len(chart_df) > 15:
            chart_df = chart_df.nlargest(15, "avg_congestion")
        if not chart_df.empty:
            df_cong = chart_df.sort_values("avg_congestion", ascending=False).copy()
            parts.append(_bar_chart_html(
                df_cong, name_col, "avg_congestion",
                "Average congestion by event (selected window)",
                "#DD4633",
            ))
            if "pct_change" in chart_df.columns:
                df_pct = chart_df.sort_values("pct_change", ascending=False).copy()
                parts.append(_bar_chart_html(
                    df_pct, name_col, "pct_change",
                    "Percent change vs baseline by event",
                    "#DD4633",
                ))
    else:
        parts.append("<p><small>Insufficient data for chart.</small></p>")
    parts.append("<hr />")

    # Time-based impact: only when "full day" is selected; otherwise skip section
    if payload and payload.get("time_window") == "full day":
        parts.append("<h2>Time-based impact</h2>")
        time_based_text = time_based_clean
        if not time_based_text and payload.get("time_window_breakdown"):
            tw_list = payload["time_window_breakdown"]
            baseline = payload.get("baseline_avg") or 0
            if tw_list and baseline:
                by_cong = max(tw_list, key=lambda x: x["avg_congestion"])
                pct_list = [
                    (w["window"], (w["avg_congestion"] - baseline) / baseline * 100)
                    for w in tw_list
                ]
                by_pct = max(pct_list, key=lambda x: x[1]) if pct_list else None
                time_based_text = (
                    f"{by_cong['window']} shows the highest average congestion ({by_cong['avg_congestion']:.2f}). "
                    + (f"The largest percent increase versus baseline is in the {by_pct[0]} window ({by_pct[1]:.1f}%)." if by_pct else "")
                )
        parts.append(f"<p>{time_based_text or '—'}</p>")
        if payload.get("time_window_breakdown"):
            tw_df = pd.DataFrame(payload["time_window_breakdown"])
            baseline = payload.get("baseline_avg") or 0
            if baseline and not tw_df.empty:
                tw_df = tw_df.copy()
                tw_df["pct_change"] = (tw_df["avg_congestion"] - baseline) / baseline * 100
            if not tw_df.empty:
                tw_cong = tw_df.sort_values("avg_congestion", ascending=False)
                parts.append(_bar_chart_html(
                    tw_cong, "window", "avg_congestion",
                    "Average congestion by time window (all filtered events)",
                    "#DD4633",
                ))
                if "pct_change" in tw_df.columns and len(tw_df) > 1:
                    tw_pct = tw_df.sort_values("pct_change", ascending=False)
                    parts.append(_bar_chart_html(
                        tw_pct, "window", "pct_change",
                        "Percent change vs baseline by time window",
                        "#DD4633",
                    ))
            else:
                parts.append("<p><small>Insufficient data for time-window chart.</small></p>")
        else:
            parts.append("<p><small>No time-window breakdown data.</small></p>")
        parts.append("<hr />")

    parts.append("<h2>Suggested actions for travel planning</h2>")
    parts.append(_format_suggested_actions(suggested_clean))
    parts.append("<hr />")

    parts.append('<div class="appendix">')
    parts.append("<h2>How conclusions were drawn</h2>")
    footnote_parts = []
    if dataset_summary:
        footnote_parts.append(dataset_summary)
    if footnotes:
        footnote_parts.append(footnotes)
    parts.append(f"<p>{' '.join(footnote_parts) or '—'}</p>")
    parts.append("</div>")

    body_html = "\n".join(parts)
    full_doc = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>{title}</title>
  <style>
{_REPORT_CSS}
  </style>
</head>
<body>
{body_html}
</body>
</html>"""

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(full_doc)

    return str(out_path)
