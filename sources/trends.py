"""Fetch Google Trends for a term and render Plotly charts (weekly and annual)."""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path
import webbrowser
import time
import random
import json
import hashlib
from utils.utils_io import slug as util_slug, resolve_effective_outdir, save_png_if_requested

import pandas as pd
import plotly.express as px
from plotly.graph_objs import Figure as PlotlyFigure
from pytrends.request import TrendReq
from pytrends.exceptions import TooManyRequestsError, ResponseError
CACHE_DIR = Path("trends_cache")
SUGGESTIONS_CACHE_FILE = CACHE_DIR / "suggestions.json"


def _ensure_cache_dir() -> None:
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass


def _hash_key(*parts: str) -> str:
    m = hashlib.md5()
    for p in parts:
        m.update(p.encode("utf-8"))
        m.update(b"::")
    return m.hexdigest()


def _load_suggestions_cache() -> dict:
    if SUGGESTIONS_CACHE_FILE.exists():
        try:
            return json.loads(SUGGESTIONS_CACHE_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_suggestions_cache(cache: dict) -> None:
    try:
        _ensure_cache_dir()
        SUGGESTIONS_CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def _ten_year_timeframe() -> str:
    today = date.today()
    try:
        start = today.replace(year=today.year - 10)
    except ValueError:
        start = today - timedelta(days=3650)
    return f"{start:%Y-%m-%d} {today:%Y-%m-%d}"


def _get_topic_mid(pytrends: TrendReq, query: str) -> str | None:
    qkey = query.strip().lower()
    cache = _load_suggestions_cache()
    if qkey in cache:
        return cache[qkey]
    try:
        sugg = pytrends.suggestions(query)
    except Exception:
        return None
    if not sugg:
        return None
    chosen = None
    for s in sugg:
        if s.get("title", "").lower() == query.lower():
            chosen = s.get("mid")
            break
    if not chosen:
        for s in sugg:
            title = s.get("title", "")
            if "fast healthcare interoperability resources" in title.lower() or title.lower() == "fhir":
                chosen = s.get("mid")
                break
    if not chosen:
        chosen = sugg[0].get("mid")
    if chosen:
        cache[qkey] = chosen
        _save_suggestions_cache(cache)
    return chosen


def _fetch_with_retries(pytrends: TrendReq, kw: str, timeframe: str, geo: str, retries: int = 3) -> pd.DataFrame:
    last_err: Exception | None = None
    for attempt in range(retries + 1):
        try:
            pytrends.build_payload([kw], timeframe=timeframe, geo=geo)
            return pytrends.interest_over_time()
        except TooManyRequestsError as e:
            last_err = e
            base = 4 * (attempt + 1)
            jitter = random.uniform(0.8, 1.4)
            wait = int(base * jitter)
            print(f"Rate limited by Google (429). Waiting {wait}s and retrying... ({attempt+1}/{retries})")
            time.sleep(wait)
        except ResponseError as e:
            last_err = e
            break
        except Exception as e:
            last_err = e
            break
    raise last_err if last_err else RuntimeError("Failed to fetch trends data")


def fetch_trends(term: str, timeframe: str = "today 5-y", geo: str = "", use_topic: bool = False, force: bool = False) -> pd.DataFrame:
    qterm = term
    pytrends = TrendReq(hl="en-US", tz=0, timeout=(10, 25))
    series_name = qterm
    if use_topic:
        mid = _get_topic_mid(pytrends, term)
        if mid:
            series_name = mid
    _ensure_cache_dir()
    cache_key = _hash_key(series_name, timeframe, geo)
    cache_path = CACHE_DIR / f"weekly_{cache_key}.csv"
    if cache_path.exists() and not force:
        try:
            df = pd.read_csv(cache_path)
            if set(["week", "interest"]).issubset(df.columns):
                return df
        except Exception:
            pass
    time.sleep(random.uniform(1.5, 3.0))
    try:
        df = _fetch_with_retries(pytrends, series_name, timeframe, geo)
    except Exception as e:
        fallback_tf = "today 5-y"
        print(f"Warning: Error fetching timeframe '{timeframe}'. Falling back to '{fallback_tf}'. Error: {e}")
        df = _fetch_with_retries(pytrends, series_name, fallback_tf, geo)
    if df.empty:
        raise RuntimeError("Google Trends returned no data. Try a broader timeframe or remove quotes.")
    df = df.reset_index().rename(columns={series_name: "interest", "date": "week"})
    if "isPartial" in df.columns:
        df = df.drop(columns=["isPartial"]) 
    try:
        df.to_csv(cache_path, index=False)
    except Exception:
        pass
    return df


def plot_trends(
    df: pd.DataFrame,
    term: str,
    output_html: Path,
    anomaly_start: str | None = None,
    anomaly_end: str | None = None,
    open_browser: bool = True,
) -> PlotlyFigure:
    fig = px.line(df, x="week", y="interest", title=f"Google Trends: {term}", labels={"week": "Week", "interest": "Search Interest (0-100)"})
    fig.update_traces(mode="lines", line=dict(color="#ff7f0e", width=2))
    fig.update_layout(template="plotly_white", hovermode="x unified")

    if anomaly_start and anomaly_end:
        fig.add_vrect(x0=anomaly_start, x1=anomaly_end, fillcolor="orange", opacity=0.15, line_width=0)
        fig.add_annotation(x=anomaly_end, y=df["interest"].max(), text="Recent peak window (normalization)",
                           showarrow=False, xanchor="left", yanchor="top", font=dict(color="orange"))

    if "interest" in df.columns:
        df_ma = df.copy()
        df_ma["ma_8w"] = df_ma["interest"].rolling(window=8, min_periods=1).mean()
        fig.add_scatter(x=df_ma["week"], y=df_ma["ma_8w"], mode="lines", name="8-week avg", line=dict(color="#1f77b4", width=2, dash="dash"))

    fig.write_html(str(output_html))
    print(f"Saved Trends chart to: {output_html}")
    if open_browser:
        try:
            webbrowser.open_new_tab(Path(output_html).resolve().as_uri())
        except Exception:
            pass
    return fig


def annualize(df: pd.DataFrame) -> pd.DataFrame:
    if "week" not in df.columns:
        raise ValueError("DataFrame missing 'week' column for annualization")
    tmp = df.copy()
    tmp["year"] = pd.to_datetime(tmp["week"]).dt.year
    out = tmp.groupby("year", as_index=False).agg(interest=("interest", "mean"))
    out["interest"] = out["interest"].round(1)
    return out


def plot_trends_annual(df_year: pd.DataFrame, term: str, output_html: Path, open_browser: bool = True) -> PlotlyFigure:
    fig = px.bar(df_year, x="year", y="interest", title=f"Google Trends (Annual Avg): {term}", labels={"year": "Year", "interest": "Avg Search Interest (0-100)"}, text="interest")
    fig.update_traces(textposition="outside", marker_color="#2ca02c")
    fig.update_layout(template="plotly_white", xaxis=dict(dtick=1), height=500)
    fig.write_html(str(output_html))
    print(f"Saved Annual Trends chart to: {output_html}")
    if open_browser:
        try:
            webbrowser.open_new_tab(Path(output_html).resolve().as_uri())
        except Exception:
            pass
    return fig


def _write_combined_iframes(output_html: Path, parts: list[tuple[str, Path]]) -> None:
    rows = []
    for title, rel in parts:
        rows.append(f"<section style=\"margin-bottom:24px;\"><h2 style=\"font-family:Arial, sans-serif;\">{title}</h2>\n"
                    f"<iframe src=\"{rel.as_posix()}\" style=\"width:100%;height:600px;border:1px solid #eee;border-radius:6px;\"></iframe>\n"
                    f"</section>")
    html = """<!doctype html>
<html>
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>Google Trends Dashboard</title>
  <style>body{max-width:1200px;margin:24px auto;padding:0 16px;color:#222}</style>
  </head>
<body>
  {content}
</body>
</html>""".replace("{content}", "\n".join(rows))
    output_html.write_text(html, encoding="utf-8")
    print(f"Saved combined Trends dashboard to: {output_html}")


def main():
    if len(sys.argv) < 2:
        print("Usage (Worldwide, one keyword):")
        print("  uv run python .\\trends.py <term> [timeframe] [anomaly_start] [anomaly_end] [--annual] [--topic] [--force] [--outdir=<path>] [--category=<name>] [--combine] [--png] [--no-open] [--no-term-subdir]")
        print("Examples (PowerShell):")
        print("  uv run python .\\trends.py FHIR --annual --topic  # Annual, last 10 years (single call via 'all'), Topic")
        print("  uv run python .\\trends.py FHIR --annual --topic --category=trends  # saves under outputs/fhir/trends/")
        print("  uv run python .\\trends.py FHIR --annual --topic --outdir=outputs/fhir/trends  # custom explicit path (term-first)")
        print("  uv run python .\\trends.py FHIR --annual --topic --outdir=outputs/trends --no-term-subdir  # save directly in outputs/trends/")
        print("  uv run python .\\trends.py FHIR --annual --topic --outdir=outputs/trends --combine --png")
        print("  uv run python .\\trends.py FHIR '2018-01-01 2025-10-31'")
        print("  uv run python .\\trends.py FHIR '2018-01-01 2025-10-31' '2024-11-01' '2025-02-28'")
        sys.exit(0)
    args = sys.argv[1:]
    use_topic = any(a == "--topic" for a in args)
    annual = any(a == "--annual" for a in args)
    force = any(a == "--force" for a in args)
    combine = any(a == "--combine" for a in args)
    save_png = any(a == "--png" for a in args)
    no_open = any(a == "--no-open" for a in args)
    no_term_subdir = any(a == "--no-term-subdir" for a in args)
    outdir_arg = next((a.split("=",1)[1] for a in args if a.startswith("--outdir=")), None)
    category_arg = next((a.split("=",1)[1] for a in args if a.startswith("--category=")), None)
    pos = [a for a in args if not a.startswith("--")]
    term = pos[0]
    if len(pos) > 1:
        timeframe = pos[1]
    else:
        timeframe = "all" if annual else "today 5-y"
    anomaly_start = pos[2] if len(pos) > 2 else None
    anomaly_end = pos[3] if len(pos) > 3 else None
    geo = ""

    df = fetch_trends(term, timeframe=timeframe, geo=geo, use_topic=use_topic, force=force)
    term_slug = util_slug(term)
    # If only a category is provided, place outputs under outputs/<term_slug>/<category>
    derived_outdir = (Path("outputs") / term_slug / category_arg) if (outdir_arg is None and category_arg) else None
    outdir = Path(outdir_arg) if outdir_arg else (derived_outdir if derived_outdir is not None else None)
    base_filename = f"trends_{term.replace('\\' , '').replace('/', '').replace(' ', '_').lower()}"
    # If we constructed a term-first derived_outdir above, avoid adding the term again
    local_no_term_subdir = no_term_subdir or (derived_outdir is not None)
    effective_outdir = resolve_effective_outdir(str(outdir) if outdir else None, term, no_term_subdir=local_no_term_subdir)
    csv_path = (effective_outdir / f"{base_filename}.csv") if effective_outdir else Path(f"{base_filename}.csv")
    df.to_csv(csv_path, index=False)
    print(f"Saved Trends data to: {csv_path}")

    if annual:
        if timeframe == "all":
            today = date.today()
            try:
                start = today.replace(year=today.year - 10)
            except ValueError:
                start = today - timedelta(days=3650)
            df = df[(pd.to_datetime(df["week"]) >= pd.to_datetime(start)) & (pd.to_datetime(df["week"]) <= pd.to_datetime(today))]
        df_year = annualize(df)
        annual_csv_path = (effective_outdir / f"trends_annual_{term.replace('\\' , '').replace('/', '').replace(' ', '_').lower()}.csv") if effective_outdir else Path(f"trends_annual_{term.replace('\\' , '').replace('/', '').replace(' ', '_').lower()}.csv")
        df_year.to_csv(annual_csv_path, index=False)
        print(f"Saved Annual Trends data to: {annual_csv_path}")
        annual_html_path = (effective_outdir / f"trends_annual_{term.replace('\\' , '').replace('/', '').replace(' ', '_').lower()}.html") if effective_outdir else Path(f"trends_annual_{term.replace('\\' , '').replace('/', '').replace(' ', '_').lower()}.html")
        fig_annual = plot_trends_annual(df_year, f"{term} (Worldwide, Topic)" if use_topic else f"{term} (Worldwide)", Path(annual_html_path), open_browser=(not no_open and not combine))
        save_png_if_requested(fig_annual, Path(annual_html_path).with_suffix(".png"), save_png)
        if combine:
            weekly_html_path = (effective_outdir / f"{base_filename}.html") if effective_outdir else Path(f"{base_filename}.html")
            fig_weekly = plot_trends(df, f"{term} (Worldwide)" + (" [Topic]" if use_topic else ""), Path(weekly_html_path), anomaly_start=anomaly_start, anomaly_end=anomaly_end, open_browser=False)
            save_png_if_requested(fig_weekly, Path(weekly_html_path).with_suffix(".png"), save_png)
            combined_path = (effective_outdir / f"trends_dashboard_{util_slug(term)}.html") if effective_outdir else Path(f"trends_dashboard_{util_slug(term)}.html")
            rel_weekly = Path(weekly_html_path.name) if effective_outdir else Path(weekly_html_path)
            rel_annual = Path(annual_html_path.name) if effective_outdir else Path(annual_html_path)
            _write_combined_iframes(combined_path, [("Weekly Search Interest", rel_weekly), ("Annual Average (Last 10 Years)", rel_annual)])
            if not no_open:
                try:
                    webbrowser.open_new_tab(combined_path.resolve().as_uri())
                except Exception:
                    pass
    else:
        html_path = (effective_outdir / f"{base_filename}.html") if effective_outdir else Path(f"{base_filename}.html")
        fig_weekly = plot_trends(df, f"{term} (Worldwide)" + (" [Topic]" if use_topic else ""), Path(html_path), anomaly_start=anomaly_start, anomaly_end=anomaly_end, open_browser=not no_open)
        save_png_if_requested(fig_weekly, Path(html_path).with_suffix(".png"), save_png)


if __name__ == "__main__":
    main()