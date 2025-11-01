"""
arXiv Preprints Data Source for HypePlot
Tracks academic paper counts by year from arXiv.org
"""

import requests
import time
import xml.etree.ElementTree as ET
from datetime import datetime
import pandas as pd
from pathlib import Path
from utils.date_utils import generate_date_buckets


def search_arxiv(query: str, start_date: datetime, end_date: datetime, max_results: int = 500) -> int:
    """
    Search arXiv papers in a date range using the arXiv API.
    
    LIMITATION: arXiv API doesn't support date filtering. We fetch recent papers
    and count those in the date range. For popular terms, this is an approximation.
    
    Args:
        query: Search term (searches title, abstract, etc.)
        start_date: Start date
        end_date: End date
        max_results: Maximum results to fetch (default 500 for speed)
    
    Returns:
        Approximate paper count in the date range
    """
    base_url = "http://export.arxiv.org/api/query"
    
    # Search in title, abstract, and keywords
    search_query = f"all:{query}"
    
    params = {
        "search_query": search_query,
        "start": 0,
        "max_results": max_results,
        "sortBy": "submittedDate",
        "sortOrder": "descending"  # Get most recent papers
    }
    
    try:
        response = requests.get(base_url, params=params, timeout=15)
        response.raise_for_status()
        
        # Parse XML response
        root = ET.fromstring(response.content)
        
        # arXiv API namespace
        ns = {
            'atom': 'http://www.w3.org/2005/Atom',
            'arxiv': 'http://arxiv.org/schemas/atom'
        }
        
        # Count papers in date range
        count = 0
        oldest_checked = None
        
        for entry in root.findall('atom:entry', ns):
            published = entry.find('atom:published', ns)
            if published is not None and published.text:
                pub_date = datetime.fromisoformat(published.text.replace('Z', '+00:00'))
                pub_date = pub_date.replace(tzinfo=None)
                
                if oldest_checked is None or pub_date < oldest_checked:
                    oldest_checked = pub_date
                
                if start_date <= pub_date <= end_date:
                    count += 1
        
        # Warn if we might be missing papers
        if oldest_checked and oldest_checked > start_date:
            print(f" (⚠️  only checked back to {oldest_checked.strftime('%Y-%m')})", end="")
        
        return count
    
    except Exception as e:
        print(f"⚠️  arXiv API error: {e}")
        return 0


def get_range(
    search_term: str, 
    start_year: int, 
    end_year: int, 
    output_file: str = "arxiv_data.csv",
    bucket_days: int = 365
):
    """
    Extract arXiv paper counts for a date range.
    
    Args:
        search_term: Search query
        start_year: Start year
        end_year: End year
        output_file: Path to output CSV file
        bucket_days: Number of days per time bucket
    """
    print(f"Searching arXiv for '{search_term}' ({start_year}-{end_year}, {bucket_days}-day buckets)...")
    
    data = []
    
    for start_date, end_date, label in generate_date_buckets(start_year, end_year, bucket_days):
        print(f"  📅 {label}...", end=" ", flush=True)
        
        count = search_arxiv(search_term, start_date, end_date)
        
        data.append({
            "period": label,
            "start_date": start_date.strftime("%Y-%m-%d"),
            "end_date": end_date.strftime("%Y-%m-%d"),
            "paper_count": count
        })
        print(f"{count} papers")
        
        # Respect arXiv rate limiting (1 request per 3 seconds)
        time.sleep(3)
    
    # Save to CSV
    df = pd.DataFrame(data)
    df.to_csv(output_file, index=False)
    print(f"\n✅ arXiv data saved to: {output_file}")
    
    return df


def visualize_data(
    csv_file: str,
    term: str,
    output_dir: str = ".",
    open_browser: bool = False,
    save_png: bool = False
):
    """
    Create visualizations for arXiv data.
    
    Args:
        csv_file: Path to CSV file with arXiv data
        term: Search term for title
        output_dir: Directory to save visualizations
        open_browser: Whether to open HTML in browser
        save_png: Whether to save PNG version
    """
    import plotly.graph_objects as go
    
    df = pd.read_csv(csv_file)
    
    # Use 'period' column for x-axis (works for yearly, monthly, quarterly, custom)
    x_values = df.get("period", df.get("year", df.index))
    
    # Calculate growth if we have paper_count column
    df['growth'] = df['paper_count'].pct_change() * 100
    
    fig = go.Figure()
    
    # Add line trace
    fig.add_trace(
        go.Scatter(
            x=x_values,
            y=df["paper_count"],
            mode="lines+markers",
            name="Papers",
            line=dict(color="#b31b1b", width=3),
            marker=dict(size=10),
            hovertemplate=(
                "<b>%{x}</b><br>" +
                "Papers: %{y:,}<br>" +
                "<extra></extra>"
            )
        )
    )
    
    # Add growth annotations for significant changes
    for idx in range(len(df)):
        if idx > 0:
            row = df.iloc[idx]
            growth = row['growth']
            if pd.notna(growth) and abs(growth) > 20:  # >20% growth
                # Get x value - handle both Series and Index
                if isinstance(x_values, pd.Series):
                    x_val = x_values.iloc[idx]
                elif isinstance(x_values, pd.Index):
                    x_val = x_values[idx]
                else:
                    x_val = x_values[idx]
                
                fig.add_annotation(
                    x=x_val,
                    y=row['paper_count'],
                    text=f"{growth:+.0f}%",
                    showarrow=True,
                    arrowhead=2,
                    arrowsize=1,
                    arrowwidth=2,
                    arrowcolor="#b31b1b",
                    ax=0,
                    ay=-40 if growth > 0 else 40,
                    font=dict(size=10, color="#b31b1b")
                )
    
    # Update layout
    fig.update_layout(
        title=f"arXiv Preprints: {term}",
        title_font_size=20,
        xaxis_title="Period",
        yaxis_title="Number of Papers",
        hovermode="x unified",
        height=600,
        showlegend=False,
        plot_bgcolor="white"
    )
    
    fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='lightgray')
    fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='lightgray')
    
    # Save HTML
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    html_file = output_path / f"{term.lower().replace(' ', '_')}_arxiv.html"
    fig.write_html(str(html_file))
    print(f"✅ arXiv chart saved: {html_file}")
    
    # Save PNG if requested
    if save_png:
        png_file = html_file.with_suffix('.png')
        try:
            fig.write_image(str(png_file), width=1200, height=600)
            print(f"✅ arXiv PNG saved: {png_file}")
        except Exception as e:
            print(f"⚠️  Could not save PNG: {e}")
    
    # Open in browser
    if open_browser:
        import webbrowser
        webbrowser.open_new_tab(html_file.resolve().as_uri())
    
    return fig


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 4:
        print("Usage: python arxiv.py '<search term>' <start_year> <end_year>")
        sys.exit(1)
    
    term = sys.argv[1]
    start = int(sys.argv[2])
    end = int(sys.argv[3])
    
    df = get_range(term, start, end)
    visualize_data("arxiv_data.csv", term, open_browser=True)
