"""
Patent Filings Data Source for HypePlot
Tracks patent applications and grants over time.

Uses USPTO (United States Patent and Trademark Office) PatentsView API.
Free, no API key required.
"""

import requests
import time
from datetime import datetime
import pandas as pd
from pathlib import Path
from utils.date_utils import generate_date_buckets


def search_patents(query: str, start_date: datetime, end_date: datetime) -> dict:
    """
    Search patents using PatentsView API.
    
    Args:
        query: Search term for patent title/abstract
        start_date: Start date
        end_date: End date
    
    Returns:
        dict with application_count, grant_count
    """
    # PatentsView API v1 (free, no auth)
    url = "https://api.patentsview.org/patents/query"
    
    # Format dates for API
    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")
    
    # Query for patents with the term in title or abstract, filed in date range
    query_json = {
        "q": {
            "_and": [
                {
                    "_or": [
                        {"_text_any": {"patent_title": query}},
                        {"_text_any": {"patent_abstract": query}}
                    ]
                },
                {"_gte": {"app_date": start_str}},
                {"_lte": {"app_date": end_str}}
            ]
        },
        "f": ["patent_number", "patent_title", "app_date", "patent_date"],
        "o": {"per_page": 25}
    }
    
    try:
        response = requests.post(url, json=query_json, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        total_count = data.get("total_patent_count", 0)
        patents = data.get("patents", [])
        
        # Count how many were granted (have patent_date)
        granted = sum(1 for p in patents if p.get("patent_date"))
        
        return {
            "application_count": total_count,
            "grant_count": granted if granted > 0 else 0
        }
    
    except Exception as e:
        print(f"⚠️  PatentsView API error: {e}")
        return {"application_count": 0, "grant_count": 0}


def get_range(search_term: str, start_year: int, end_year: int, output_file: str = "patents_data.csv",
    bucket_days: int = 365
):
    """
    Extract patent statistics for a date range.
    
    Args:
        search_term: Technology or concept to search for
        start_year: Start year
        end_year: End year
        output_file: Path to output CSV file
        bucket_days: Number of days per time bucket
    """
    print(f"Searching USPTO patents for '{search_term}' ({start_year}-{end_year}, {bucket_days}-day buckets)...")
    print("Note: Using PatentsView API (US patents only)")
    
    data = []
    
    for start_date, end_date, label in generate_date_buckets(start_year, end_year, bucket_days):
        print(f"  📅 {label}...", end=" ", flush=True)
        
        result = search_patents(search_term, start_date, end_date)
        
        row = {
            "period": label,
            "start_date": start_date.strftime("%Y-%m-%d"),
            "end_date": end_date.strftime("%Y-%m-%d"),
            "application_count": result["application_count"],
            "grant_count": result["grant_count"]
        }
        
        data.append(row)
        print(f"✓ {result['application_count']} applications, {result['grant_count']} grants")
        
        # Be respectful to the API
        time.sleep(2)
    
    # Save to CSV
    df = pd.DataFrame(data)
    df.to_csv(output_file, index=False)
    print(f"\n✅ Patent data saved to: {output_file}")
    
    return df


def visualize_data(
    csv_file: str,
    term: str,
    output_dir: str = ".",
    open_browser: bool = False,
    save_png: bool = False
):
    """
    Create visualizations for patent data.
    """
    import plotly.graph_objects as go
    
    df = pd.read_csv(csv_file)
    
    fig = go.Figure()
    
    # Applications
    fig.add_trace(
        go.Scatter(
            x=df.get("period", df.get("year", df.index)),
            y=df["application_count"],
            mode="lines+markers",
            name="Applications",
            line=dict(color="#7c3aed", width=3),
            marker=dict(size=10),
            hovertemplate="<b>%{x}</b><br>Applications: %{y:,}<extra></extra>"
        )
    )
    
    # Grants
    fig.add_trace(
        go.Scatter(
            x=df.get("period", df.get("year", df.index)),
            y=df["grant_count"],
            mode="lines+markers",
            name="Grants",
            line=dict(color="#059669", width=3, dash="dash"),
            marker=dict(size=8),
            hovertemplate="<b>%{x}</b><br>Grants: %{y:,}<extra></extra>"
        )
    )
    
    fig.update_layout(
        title=f"Patent Activity: {term}",
        title_font_size=20,
        xaxis_title="Period",
        yaxis_title="Count",
        hovermode="x unified",
        height=600,
        showlegend=True,
        plot_bgcolor="white"
    )
    
    fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='lightgray')
    fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='lightgray')
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    html_file = output_path / f"{term.lower().replace(' ', '_')}_patents.html"
    fig.write_html(str(html_file))
    print(f"✅ Patents chart saved: {html_file}")
    
    if save_png:
        png_file = html_file.with_suffix('.png')
        try:
            fig.write_image(str(png_file), width=1200, height=600)
            print(f"✅ Patents PNG saved: {png_file}")
        except Exception as e:
            print(f"⚠️  Could not save PNG: {e}")
    
    if open_browser:
        import webbrowser
        webbrowser.open_new_tab(html_file.resolve().as_uri())
    
    return fig


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 4:
        print("Usage: python patents.py '<search term>' <start_year> <end_year>")
        sys.exit(1)
    
    term = sys.argv[1]
    start = int(sys.argv[2])
    end = int(sys.argv[3])
    
    df = get_range(term, start, end)
    visualize_data("patents_data.csv", term, open_browser=True)
