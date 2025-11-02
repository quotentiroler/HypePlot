"""
GitHub Activity Data Source for HypePlot
Tracks repository counts, stars, forks, and activity over time.
"""

import requests
import time
import pandas as pd
from datetime import datetime
from pathlib import Path
from utils.date_utils import generate_date_buckets


def search_repositories(query: str, start_date: datetime, end_date: datetime, per_page: int = 100) -> dict:
    """
    Search GitHub repositories created in a specific date range.
    
    Args:
        query: Search term
        start_date: Start date for created range
        end_date: End date for created range
        per_page: Results per page (max 100)
    
    Returns:
        dict with total_count, items (repos), and aggregated stats
    """
    # GitHub Search API
    url = "https://api.github.com/search/repositories"
    
    # Query: topic OR name OR description, created in specific date range
    search_query = f"{query} created:{start_date.strftime('%Y-%m-%d')}..{end_date.strftime('%Y-%m-%d')}"
    
    params = {
        "q": search_query,
        "sort": "stars",
        "order": "desc",
        "per_page": per_page,
        "page": 1
    }
    
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "HypePlot-Academic-Tracker"
    }
    
    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # Aggregate stats from returned repos
        total_stars = sum(repo.get("stargazers_count", 0) for repo in data.get("items", []))
        total_forks = sum(repo.get("forks_count", 0) for repo in data.get("items", []))
        total_watchers = sum(repo.get("watchers_count", 0) for repo in data.get("items", []))
        
        return {
            "total_count": data.get("total_count", 0),
            "total_stars": total_stars,
            "total_forks": total_forks,
            "total_watchers": total_watchers,
            "items": data.get("items", [])
        }
    
    except requests.exceptions.RequestException as e:
        print(f"⚠️  GitHub API error for {start_date.strftime('%Y-%m-%d')}: {e}")
        return {
            "total_count": 0,
            "total_stars": 0,
            "total_forks": 0,
            "total_watchers": 0,
            "items": []
        }


def get_range(
    search_term: str, 
    start_year: int, 
    end_year: int, 
    bucket_days: int = 365
) -> pd.DataFrame:
    """
    Extract GitHub repository statistics for a date range.
    
    Args:
        search_term: Search query
        start_year: Start year
        end_year: End year
        bucket_days: Number of days per time bucket
        
    Returns:
        DataFrame with repository statistics per time period
    """
    print(f"Searching GitHub for '{search_term}' ({start_year}-{end_year}, {bucket_days}-day buckets)...")
    
    data = []
    
    for start_date, end_date, label in generate_date_buckets(start_year, end_year, bucket_days):
        print(f"  📅 {label}...", end=" ", flush=True)
        
        result = search_repositories(search_term, start_date, end_date)
        
        row = {
            "period": label,
            "start_date": start_date.strftime("%Y-%m-%d"),
            "end_date": end_date.strftime("%Y-%m-%d"),
            "repo_count": result["total_count"],
            "total_stars": result["total_stars"],
            "total_forks": result["total_forks"],
            "total_watchers": result["total_watchers"]
        }
        
        data.append(row)
        print(f"✓ {result['total_count']} repos, {result['total_stars']:,} stars")
        
        # Rate limiting: GitHub allows 10 requests/min for unauthenticated
        # 6 seconds = 10 requests per minute
        time.sleep(6)
    
    # Return DataFrame (caller handles CSV saving)
    df = pd.DataFrame(data)
    return df


def visualize_data(
    csv_file: str,
    term: str,
    output_dir: str = ".",
    open_browser: bool = False,
    save_png: bool = False
):
    """
    Create visualizations for GitHub data.
    
    Args:
        csv_file: Path to CSV file with GitHub data
        term: Search term for title
        output_dir: Directory to save visualizations
        open_browser: Whether to open HTML in browser
        save_png: Whether to save PNG version
    """
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    
    df = pd.read_csv(csv_file)
    
    # Create subplots: 2 rows
    fig = make_subplots(
        rows=2, cols=1,
        subplot_titles=(
            f"GitHub Repository Count: {term}",
            f"GitHub Community Engagement: {term}"
        ),
        vertical_spacing=0.15
    )
    
    # Use 'period' column for x-axis (works for yearly, monthly, quarterly, custom)
    x_values = df.get("period", df.get("year", df.index))
    
    # Row 1: Repository count
    fig.add_trace(
        go.Scatter(
            x=x_values,
            y=df["repo_count"],
            mode="lines+markers",
            name="Repositories",
            line=dict(color="#24292e", width=3),
            marker=dict(size=8),
            hovertemplate="<b>%{x}</b><br>Repos: %{y:,}<extra></extra>"
        ),
        row=1, col=1
    )
    
    # Row 2: Stars and Forks
    fig.add_trace(
        go.Scatter(
            x=x_values,
            y=df["total_stars"],
            mode="lines+markers",
            name="Total Stars",
            line=dict(color="#f97316", width=3),
            marker=dict(size=8),
            hovertemplate="<b>%{x}</b><br>Stars: %{y:,}<extra></extra>"
        ),
        row=2, col=1
    )
    
    fig.add_trace(
        go.Scatter(
            x=x_values,
            y=df["total_forks"],
            mode="lines+markers",
            name="Total Forks",
            line=dict(color="#8b5cf6", width=3),
            marker=dict(size=8),
            hovertemplate="<b>%{x}</b><br>Forks: %{y:,}<extra></extra>"
        ),
        row=2, col=1
    )
    
    # Update layout
    fig.update_layout(
        height=800,
        showlegend=True,
        title_text=f"GitHub Activity: {term}",
        title_font_size=20,
        hovermode="x unified"
    )
    
    fig.update_xaxes(title_text="Period", row=2, col=1)
    fig.update_yaxes(title_text="Repository Count", row=1, col=1)
    fig.update_yaxes(title_text="Count", row=2, col=1)
    
    # Save HTML
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    html_file = output_path / f"{term.lower().replace(' ', '_')}_github.html"
    fig.write_html(str(html_file))
    print(f"✅ GitHub chart saved: {html_file}")
    
    # Save PNG if requested
    if save_png:
        png_file = html_file.with_suffix('.png')
        try:
            fig.write_image(str(png_file), width=1200, height=800)
            print(f"✅ GitHub PNG saved: {png_file}")
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
        print("Usage: python github.py '<search term>' <start_year> <end_year>")
        sys.exit(1)
    
    term = sys.argv[1]
    start = int(sys.argv[2])
    end = int(sys.argv[3])
    
    df = get_range(term, start, end)
    visualize_data("github_data.csv", term, open_browser=True)
