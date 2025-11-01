"""
Reddit Activity Data Source for HypePlot
Tracks post and comment frequency, upvote trends.

Note: Requires Reddit API credentials. Set via environment variables:
  REDDIT_CLIENT_ID=your_client_id
  REDDIT_CLIENT_SECRET=your_secret
  REDDIT_USER_AGENT=HypePlot/1.0
  
Register your app at: https://www.reddit.com/prefs/apps
"""

import os
import time
from datetime import datetime, timedelta
import pandas as pd
from pathlib import Path
from utils.date_utils import generate_date_buckets


def search_reddit_pushshift(query: str, start_date: datetime, end_date: datetime) -> dict:
    """
    Search Reddit using Pushshift API for a specific date range.
    
    Args:
        query: Search term
        start_date: Start date
        end_date: End date
    
    Returns:
        dict with {post_count, total_score, avg_score}
    """
    import requests
    
    # Convert to Unix timestamp
    start_ts = int(start_date.timestamp())
    end_ts = int(end_date.timestamp())
    
    # Use Pushshift API (Reddit archive)
    url = "https://api.pushshift.io/reddit/search/submission"
    params = {
        "q": query,
        "after": start_ts,
        "before": end_ts,
        "size": 100,  # Get up to 100 posts
    }
    
    try:
        response = requests.get(url, params=params, timeout=15)
        if response.status_code == 200:
            data = response.json()
            posts = data.get("data", [])
            post_count = len(posts)
            total_score = sum(p.get("score", 0) for p in posts)
            avg_score = total_score / post_count if post_count > 0 else 0
            
            return {
                "post_count": post_count,
                "total_score": total_score,
                "avg_score": avg_score
            }
        else:
            return {"post_count": 0, "total_score": 0, "avg_score": 0}
    
    except Exception as e:
        print(f"⚠️  Error: {e}")
        return {"post_count": 0, "total_score": 0, "avg_score": 0}


def get_range(search_term: str, start_year: int, end_year: int, output_file: str = "reddit_data.csv",
    bucket_days: int = 365
):
    """
    Extract Reddit activity statistics for a date range.
    
    Args:
        search_term: Search query
        start_year: Start year
        end_year: End year
        output_file: Path to output CSV file
        bucket_days: Number of days per time bucket
    """
    print(f"Searching Reddit for '{search_term}' ({start_year}-{end_year}, {bucket_days}-day buckets)...")
    print("Note: Using Pushshift API (Reddit archive). May have delays.")
    
    # Convert to DataFrame
    data = []
    for start_date, end_date, label in generate_date_buckets(start_year, end_year, bucket_days):
        print(f"  📅 {label}...", end=" ", flush=True)
        
        stats = search_reddit_pushshift(search_term, start_date, end_date)
        data.append({
            "period": label,
            "start_date": start_date.strftime("%Y-%m-%d"),
            "end_date": end_date.strftime("%Y-%m-%d"),
            "post_count": stats["post_count"],
            "total_score": stats["total_score"],
            "avg_score": int(stats["avg_score"])
        })
        print(f"✓ {stats['post_count']} posts")
        
        time.sleep(1)  # Be respectful to Pushshift API
    
    # Save to CSV
    df = pd.DataFrame(data)
    df.to_csv(output_file, index=False)
    print(f"\n✅ Reddit data saved to: {output_file}")
    
    return df


def visualize_data(
    csv_file: str,
    term: str,
    output_dir: str = ".",
    open_browser: bool = False,
    save_png: bool = False
):
    """
    Create visualizations for Reddit data.
    
    Args:
        csv_file: Path to CSV file with Reddit data
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
            f"Reddit Post Count: {term}",
            f"Reddit Engagement: {term}"
        ),
        vertical_spacing=0.15
    )
    
    # Row 1: Post count
    fig.add_trace(
        go.Scatter(
            x=df.get("period", df.get("year", df.index)),
            y=df["post_count"],
            mode="lines+markers",
            name="Posts",
            line=dict(color="#FF4500", width=3),
            marker=dict(size=8),
            hovertemplate="<b>%{x}</b><br>Posts: %{y:,}<extra></extra>"
        ),
        row=1, col=1
    )
    
    # Row 2: Total and Average Score
    fig.add_trace(
        go.Scatter(
            x=df.get("period", df.get("year", df.index)),
            y=df["total_score"],
            mode="lines+markers",
            name="Total Score",
            line=dict(color="#FF4500", width=3),
            marker=dict(size=8),
            hovertemplate="<b>%{x}</b><br>Total Score: %{y:,}<extra></extra>"
        ),
        row=2, col=1
    )
    
    fig.add_trace(
        go.Scatter(
            x=df.get("period", df.get("year", df.index)),
            y=df["avg_score"],
            mode="lines+markers",
            name="Avg Score/Post",
            line=dict(color="#FF8C42", width=2, dash="dash"),
            marker=dict(size=6),
            hovertemplate="<b>%{x}</b><br>Avg Score: %{y:,.0f}<extra></extra>",
            yaxis="y3"
        ),
        row=2, col=1
    )
    
    # Update layout
    fig.update_layout(
        height=800,
        showlegend=True,
        title_text=f"Reddit Activity: {term}",
        title_font_size=20,
        hovermode="x unified"
    )
    
    fig.update_xaxes(title_text="Period", row=2, col=1)
    fig.update_yaxes(title_text="Post Count", row=1, col=1)
    fig.update_yaxes(title_text="Total Score", row=2, col=1)
    
    # Save HTML
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    html_file = output_path / f"{term.lower().replace(' ', '_')}_reddit.html"
    fig.write_html(str(html_file))
    print(f"✅ Reddit chart saved: {html_file}")
    
    # Save PNG if requested
    if save_png:
        png_file = html_file.with_suffix('.png')
        try:
            fig.write_image(str(png_file), width=1200, height=800)
            print(f"✅ Reddit PNG saved: {png_file}")
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
        print("Usage: python reddit.py '<search term>' <start_year> <end_year>")
        sys.exit(1)
    
    term = sys.argv[1]
    start = int(sys.argv[2])
    end = int(sys.argv[3])
    
    df = get_range(term, start, end)
    visualize_data("reddit_data.csv", term, open_browser=True)
