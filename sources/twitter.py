"""
Twitter/X Mentions Data Source for HypePlot
Tracks tweet volume and engagement over time.

Note: Requires Twitter API v2 credentials. Set via environment variables:
  TWITTER_BEARER_TOKEN=your_bearer_token
  
Get API access at: https://developer.twitter.com/
"""

import requests
import time
import os
from datetime import datetime, timedelta
import pandas as pd
from pathlib import Path
from utils.date_utils import generate_date_buckets


def search_tweets(query: str, start_date: str, end_date: str, bearer_token: str) -> dict:
    """
    Search tweets using Twitter API v2.
    
    Args:
        query: Search query
        start_date: Start date (ISO 8601)
        end_date: End date (ISO 8601)
        bearer_token: Twitter API Bearer token
    
    Returns:
        dict with tweet_count, engagement metrics
    """
    url = "https://api.twitter.com/2/tweets/counts/all"
    
    headers = {
        "Authorization": f"Bearer {bearer_token}"
    }
    
    params = {
        "query": query,
        "start_time": start_date,
        "end_time": end_date,
        "granularity": "day"
    }
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # Sum up all tweet counts
        total_tweets = sum(item.get("tweet_count", 0) for item in data.get("data", []))
        
        return {
            "tweet_count": total_tweets,
            "data_points": len(data.get("data", []))
        }
    
    except Exception as e:
        print(f"⚠️  Twitter API error: {e}")
        return {"tweet_count": 0, "data_points": 0}


def get_range(search_term: str, start_year: int, end_year: int, output_file: str = "twitter_data.csv",
    bucket_days: int = 365
):
    """
    Extract Twitter mention statistics for a date range.
    
    Args:
        search_term: Search query
        start_year: Start year
        end_year: End year
        output_file: Path to output CSV file
        bucket_days: Number of days per time bucket
    """
    # Check for API token
    bearer_token = os.environ.get("TWITTER_BEARER_TOKEN")
    if not bearer_token:
        print("⚠️  ERROR: TWITTER_BEARER_TOKEN environment variable not set!")
        print("   Get API access at: https://developer.twitter.com/")
        print("   Then set it: $env:TWITTER_BEARER_TOKEN=\"your_token\" (PowerShell)")
        
        # Create empty CSV
        data = []
        for bucket_start, bucket_end, bucket_label in generate_date_buckets(start_year, end_year, bucket_days):
            data.append({
                "period": bucket_label,
                "start_date": bucket_start.strftime("%Y-%m-%d"),
                "end_date": bucket_end.strftime("%Y-%m-%d"),
                "tweet_count": 0
            })
        df = pd.DataFrame(data)
        df.to_csv(output_file, index=False)
        return df
    
    print(f"Searching Twitter/X for '{search_term}' ({start_year}-{end_year}, {bucket_days}-day buckets)...")
    
    data = []
    
    for start_date, end_date, label in generate_date_buckets(start_year, end_year, bucket_days):
        print(f"  📅 {label}...", end=" ", flush=True)
        
        # Format dates for Twitter API
        start_date_str = start_date.strftime("%Y-%m-%dT00:00:00Z")
        end_date_str = end_date.strftime("%Y-%m-%dT23:59:59Z")
        
        result = search_tweets(search_term, start_date_str, end_date_str, bearer_token)
        
        row = {
            "period": label,
            "start_date": start_date.strftime("%Y-%m-%d"),
            "end_date": end_date.strftime("%Y-%m-%d"),
            "tweet_count": result["tweet_count"]
        }
        
        data.append(row)
        print(f"✓ {result['tweet_count']:,} tweets")
        
        # Twitter API rate limiting
        time.sleep(1)
    
    # Save to CSV
    df = pd.DataFrame(data)
    df.to_csv(output_file, index=False)
    print(f"\n✅ Twitter data saved to: {output_file}")
    
    return df


def visualize_data(
    csv_file: str,
    term: str,
    output_dir: str = ".",
    open_browser: bool = False,
    save_png: bool = False
):
    """
    Create visualizations for Twitter data.
    """
    import plotly.graph_objects as go
    
    df = pd.read_csv(csv_file)
    
    fig = go.Figure()
    
    fig.add_trace(
        go.Scatter(
            x=df.get("period", df.get("year", df.index)),
            y=df["tweet_count"],
            mode="lines+markers",
            name="Tweets",
            line=dict(color="#1DA1F2", width=3),
            marker=dict(size=10),
            hovertemplate="<b>%{x}</b><br>Tweets: %{y:,}<extra></extra>"
        )
    )
    
    fig.update_layout(
        title=f"Twitter/X Mentions: {term}",
        title_font_size=20,
        xaxis_title="Period",
        yaxis_title="Tweet Count",
        hovermode="x unified",
        height=600,
        plot_bgcolor="white"
    )
    
    fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='lightgray')
    fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='lightgray')
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    html_file = output_path / f"{term.lower().replace(' ', '_')}_twitter.html"
    fig.write_html(str(html_file))
    print(f"✅ Twitter chart saved: {html_file}")
    
    if save_png:
        png_file = html_file.with_suffix('.png')
        try:
            fig.write_image(str(png_file), width=1200, height=600)
            print(f"✅ Twitter PNG saved: {png_file}")
        except Exception as e:
            print(f"⚠️  Could not save PNG: {e}")
    
    if open_browser:
        import webbrowser
        webbrowser.open_new_tab(html_file.resolve().as_uri())
    
    return fig


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 4:
        print("Usage: python twitter.py '<search term>' <start_year> <end_year>")
        sys.exit(1)
    
    term = sys.argv[1]
    start = int(sys.argv[2])
    end = int(sys.argv[3])
    
    df = get_range(term, start, end)
    visualize_data("twitter_data.csv", term, open_browser=True)
