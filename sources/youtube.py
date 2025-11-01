"""
YouTube Content Data Source for HypePlot
Tracks video counts and view statistics over time.

Note: Requires YouTube Data API v3 key. Set via environment variable:
  YOUTUBE_API_KEY=your_key_here
  
Get a free API key at: https://console.cloud.google.com/apis/credentials
"""

import requests
import time
import os
from datetime import datetime
import pandas as pd
from pathlib import Path
from utils.date_utils import generate_date_buckets


def search_videos(query: str, start_date: datetime, end_date: datetime, api_key: str, max_results: int = 50) -> dict:
    """
    Search YouTube videos published in a specific date range.
    
    Args:
        query: Search term
        start_date: Start date for published range
        end_date: End date for published range
        api_key: YouTube Data API v3 key
        max_results: Results per page (max 50)
    
    Returns:
        dict with video_count, total_views, video_ids
    """
    base_url = "https://www.googleapis.com/youtube/v3/search"
    
    # Format dates for API
    published_after = start_date.strftime("%Y-%m-%dT00:00:00Z")
    published_before = end_date.strftime("%Y-%m-%dT23:59:59Z")
    
    params = {
        "part": "snippet",
        "q": query,
        "type": "video",
        "publishedAfter": published_after,
        "publishedBefore": published_before,
        "maxResults": max_results,
        "key": api_key,
        "order": "viewCount"  # Most viewed first
    }
    
    try:
        response = requests.get(base_url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        items = data.get("items", [])
        video_ids = [item["id"]["videoId"] for item in items if "videoId" in item.get("id", {})]
        video_count = data.get("pageInfo", {}).get("totalResults", 0)
        
        # Get detailed stats (views) for these videos
        total_views = 0
        if video_ids:
            total_views = get_video_statistics(video_ids, api_key)
        
        return {
            "video_count": video_count,
            "total_views": total_views,
            "avg_views": total_views / len(video_ids) if video_ids else 0,
            "video_ids": video_ids
        }
    
    except requests.exceptions.RequestException as e:
        print(f"⚠️  YouTube API error: {e}")
        return {
            "video_count": 0,
            "total_views": 0,
            "avg_views": 0,
            "video_ids": []
        }


def get_video_statistics(video_ids: list[str], api_key: str) -> int:
    """
    Get view counts for a list of video IDs.
    
    Args:
        video_ids: List of YouTube video IDs
        api_key: YouTube Data API v3 key
    
    Returns:
        Total view count across all videos
    """
    base_url = "https://www.googleapis.com/youtube/v3/videos"
    
    # YouTube API allows up to 50 IDs per request
    total_views = 0
    
    for i in range(0, len(video_ids), 50):
        batch = video_ids[i:i+50]
        params = {
            "part": "statistics",
            "id": ",".join(batch),
            "key": api_key
        }
        
        try:
            response = requests.get(base_url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            for item in data.get("items", []):
                stats = item.get("statistics", {})
                views = int(stats.get("viewCount", 0))
                total_views += views
            
            time.sleep(0.1)  # Small delay between batches
        
        except Exception as e:
            print(f"⚠️  Error fetching video statistics: {e}")
    
    return total_views


def get_range(
    search_term: str, 
    start_year: int, 
    end_year: int, 
    output_file: str = "youtube_data.csv",
    bucket_days: int = 365
):
    """
    Extract YouTube video statistics for a date range.
    
    Args:
        search_term: Search query
        start_year: Start year
        end_year: End year
        output_file: Path to output CSV file
        bucket_days: Number of days per time bucket
    """
    # Check for API key
    api_key = os.environ.get("YOUTUBE_API_KEY")
    if not api_key:
        print("⚠️  ERROR: YOUTUBE_API_KEY environment variable not set!")
        print("   Get a free API key at: https://console.cloud.google.com/apis/credentials")
        print("   Then set it: $env:YOUTUBE_API_KEY=\"your_key_here\" (PowerShell)")
        
        # Create empty CSV
        data = []
        for start_date, end_date, label in generate_date_buckets(start_year, end_year, bucket_days):
            data.append({
                "period": label,
                "start_date": start_date.strftime("%Y-%m-%d"),
                "end_date": end_date.strftime("%Y-%m-%d"), 
                "video_count": 0, 
                "total_views": 0, 
                "avg_views": 0
            })
        df = pd.DataFrame(data)
        df.to_csv(output_file, index=False)
        return df
    
    print(f"Searching YouTube for '{search_term}' ({start_year}-{end_year}, {bucket_days}-day buckets)...")
    
    data = []
    
    for start_date, end_date, label in generate_date_buckets(start_year, end_year, bucket_days):
        print(f"  📅 {label}...", end=" ", flush=True)
        
        result = search_videos(search_term, start_date, end_date, api_key)
        
        row = {
            "period": label,
            "start_date": start_date.strftime("%Y-%m-%d"),
            "end_date": end_date.strftime("%Y-%m-%d"),
            "video_count": result["video_count"],
            "total_views": result["total_views"],
            "avg_views": int(result["avg_views"])
        }
        
        data.append(row)
        print(f"✓ {result['video_count']} videos, {result['total_views']:,} total views")
        
        # YouTube API quota: 10,000 units/day
        # Search = 100 units, Videos = 1 unit
        # Rate limiting: ~1 request per second
        time.sleep(1)
    
    # Save to CSV
    df = pd.DataFrame(data)
    df.to_csv(output_file, index=False)
    print(f"\n✅ YouTube data saved to: {output_file}")
    
    return df


def visualize_data(
    csv_file: str,
    term: str,
    output_dir: str = ".",
    open_browser: bool = False,
    save_png: bool = False
):
    """
    Create visualizations for YouTube data.
    
    Args:
        csv_file: Path to CSV file with YouTube data
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
            f"YouTube Video Count: {term}",
            f"YouTube View Statistics: {term}"
        ),
        vertical_spacing=0.15
    )
    
    # Row 1: Video count
    fig.add_trace(
        go.Scatter(
            x=df.get("period", df.get("year", df.index)),
            y=df["video_count"],
            mode="lines+markers",
            name="Videos",
            line=dict(color="#FF0000", width=3),
            marker=dict(size=8),
            hovertemplate="<b>%{x}</b><br>Videos: %{y:,}<extra></extra>"
        ),
        row=1, col=1
    )
    
    # Row 2: Total and Average Views
    fig.add_trace(
        go.Scatter(
            x=df.get("period", df.get("year", df.index)),
            y=df["total_views"],
            mode="lines+markers",
            name="Total Views",
            line=dict(color="#FF0000", width=3),
            marker=dict(size=8),
            hovertemplate="<b>%{x}</b><br>Total Views: %{y:,}<extra></extra>"
        ),
        row=2, col=1
    )
    
    fig.add_trace(
        go.Scatter(
            x=df.get("period", df.get("year", df.index)),
            y=df["avg_views"],
            mode="lines+markers",
            name="Avg Views/Video",
            line=dict(color="#FF6B6B", width=2, dash="dash"),
            marker=dict(size=6),
            hovertemplate="<b>%{x}</b><br>Avg Views: %{y:,.0f}<extra></extra>",
            yaxis="y3"
        ),
        row=2, col=1
    )
    
    # Update layout
    fig.update_layout(
        height=800,
        showlegend=True,
        title_text=f"YouTube Content: {term}",
        title_font_size=20,
        hovermode="x unified"
    )
    
    fig.update_xaxes(title_text="Period", row=2, col=1)
    fig.update_yaxes(title_text="Video Count", row=1, col=1)
    fig.update_yaxes(title_text="Total Views", row=2, col=1)
    
    # Save HTML
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    html_file = output_path / f"{term.lower().replace(' ', '_')}_youtube.html"
    fig.write_html(str(html_file))
    print(f"✅ YouTube chart saved: {html_file}")
    
    # Save PNG if requested
    if save_png:
        png_file = html_file.with_suffix('.png')
        try:
            fig.write_image(str(png_file), width=1200, height=800)
            print(f"✅ YouTube PNG saved: {png_file}")
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
        print("Usage: python youtube.py '<search term>' <start_year> <end_year>")
        sys.exit(1)
    
    term = sys.argv[1]
    start = int(sys.argv[2])
    end = int(sys.argv[3])
    
    df = get_range(term, start, end)
    visualize_data("youtube_data.csv", term, open_browser=True)
