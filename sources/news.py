"""
News Articles Data Source for HypePlot
Tracks media mention frequency using NewsAPI.

Note: Requires NewsAPI key. Set via environment variable:
  NEWS_API_KEY=your_key_here
  
Get a free API key at: https://newsapi.org/register
"""

import requests
import time
import os
from datetime import datetime, timedelta
import pandas as pd
from pathlib import Path
from utils.date_utils import generate_date_buckets


def search_news(query: str, from_date: str, to_date: str, api_key: str) -> dict:
    """
    Search news articles using NewsAPI.
    
    Args:
        query: Search term
        from_date: Start date (YYYY-MM-DD)
        to_date: End date (YYYY-MM-DD)
        api_key: NewsAPI key
    
    Returns:
        dict with article_count, sources
    """
    url = "https://newsapi.org/v2/everything"
    
    params = {
        "q": query,
        "from": from_date,
        "to": to_date,
        "sortBy": "relevancy",
        "pageSize": 100,  # Max allowed
        "apiKey": api_key,
        "language": "en"
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        total_results = data.get("totalResults", 0)
        articles = data.get("articles", [])
        
        # Count unique sources
        sources = set(article.get("source", {}).get("name", "Unknown") for article in articles)
        
        return {
            "article_count": total_results,
            "source_count": len(sources),
            "sources": list(sources)
        }
    
    except Exception as e:
        print(f"⚠️  NewsAPI error: {e}")
        return {
            "article_count": 0,
            "source_count": 0,
            "sources": []
        }


def get_range(
    search_term: str, 
    start_year: int, 
    end_year: int, 
    output_file: str = "news_data.csv",
    bucket_days: int = 365
):
    """
    Extract news article statistics for a date range.
    
    Args:
        search_term: Search query
        start_year: Start year
        end_year: End year
        output_file: Path to output CSV file
        bucket_days: Number of days per time bucket
    """
    # Check for API key
    api_key = os.environ.get("NEWS_API_KEY")
    if not api_key:
        print("⚠️  ERROR: NEWS_API_KEY environment variable not set!")
        print("   Get a free API key at: https://newsapi.org/register")
        print("   Then set it: $env:NEWS_API_KEY=\"your_key_here\" (PowerShell)")
        
        # Create empty CSV
        data = []
        for start_date, end_date, label in generate_date_buckets(start_year, end_year, bucket_days):
            data.append({
                "period": label,
                "start_date": start_date.strftime("%Y-%m-%d"),
                "end_date": end_date.strftime("%Y-%m-%d"),
                "article_count": 0,
                "source_count": 0
            })
        df = pd.DataFrame(data)
        df.to_csv(output_file, index=False)
        return df
    
    print(f"Searching news articles for '{search_term}' ({start_year}-{end_year}, {bucket_days}-day buckets)...")
    
    data = []
    current_date = datetime.now()
    
    for start_date, end_date, label in generate_date_buckets(start_year, end_year, bucket_days):
        print(f"  📅 {label}...", end=" ", flush=True)
        
        # NewsAPI free tier only allows queries from last 30 days
        # For older data, we'll return 0 or require paid plan
        from_date = start_date.strftime("%Y-%m-%d")
        to_date = end_date.strftime("%Y-%m-%d")
        
        # Check if date range is too old for free tier (older than 1 month)
        if end_date < current_date - timedelta(days=30):
            # Free tier doesn't support historical data beyond 1 month
            print(f"⚠️  Historical data requires paid NewsAPI plan")
            result = {"article_count": 0, "source_count": 0, "sources": []}
        else:
            result = search_news(search_term, from_date, to_date, api_key)
        
        row = {
            "period": label,
            "start_date": from_date,
            "end_date": to_date,
            "article_count": result["article_count"],
            "source_count": result["source_count"]
        }
        
        data.append(row)
        print(f"✓ {result['article_count']} articles from {result['source_count']} sources")
        
        # NewsAPI rate limiting: 100 requests per day for free tier
        time.sleep(1)
    
    # Save to CSV
    df = pd.DataFrame(data)
    df.to_csv(output_file, index=False)
    print(f"\n✅ News data saved to: {output_file}")
    
    return df


def visualize_data(
    csv_file: str,
    term: str,
    output_dir: str = ".",
    open_browser: bool = False,
    save_png: bool = False
):
    """
    Create visualizations for news data.
    
    Args:
        csv_file: Path to CSV file with news data
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
            f"News Article Count: {term}",
            f"News Source Diversity: {term}"
        ),
        vertical_spacing=0.15
    )
    
    # Row 1: Article count
    fig.add_trace(
        go.Scatter(
            x=df.get("period", df.get("year", df.index)),
            y=df["article_count"],
            mode="lines+markers",
            name="Articles",
            line=dict(color="#1e40af", width=3),
            marker=dict(size=8),
            hovertemplate="<b>%{x}</b><br>Articles: %{y:,}<extra></extra>"
        ),
        row=1, col=1
    )
    
    # Row 2: Source count
    fig.add_trace(
        go.Scatter(
            x=df.get("period", df.get("year", df.index)),
            y=df["source_count"],
            mode="lines+markers",
            name="Unique Sources",
            line=dict(color="#059669", width=3),
            marker=dict(size=8),
            hovertemplate="<b>%{x}</b><br>Sources: %{y:,}<extra></extra>"
        ),
        row=2, col=1
    )
    
    # Update layout
    fig.update_layout(
        height=800,
        showlegend=True,
        title_text=f"News Coverage: {term}",
        title_font_size=20,
        hovermode="x unified"
    )
    
    fig.update_xaxes(title_text="Period", row=2, col=1)
    fig.update_yaxes(title_text="Article Count", row=1, col=1)
    fig.update_yaxes(title_text="Source Count", row=2, col=1)
    
    # Save HTML
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    html_file = output_path / f"{term.lower().replace(' ', '_')}_news.html"
    fig.write_html(str(html_file))
    print(f"✅ News chart saved: {html_file}")
    
    # Save PNG if requested
    if save_png:
        png_file = html_file.with_suffix('.png')
        try:
            fig.write_image(str(png_file), width=1200, height=800)
            print(f"✅ News PNG saved: {png_file}")
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
        print("Usage: python news.py '<search term>' <start_year> <end_year>")
        sys.exit(1)
    
    term = sys.argv[1]
    start = int(sys.argv[2])
    end = int(sys.argv[3])
    
    df = get_range(term, start, end)
    visualize_data("news_data.csv", term, open_browser=True)
