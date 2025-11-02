"""
NSF Grants Data Source for HypePlot
Tracks research grant funding from the National Science Foundation.

Uses NSF Awards API (free, no authentication required):
https://www.research.gov/common/webapi/awardapisearch-v1.htm
"""

from __future__ import annotations
import requests
import time
from datetime import datetime
import pandas as pd
from pathlib import Path
from utils.date_utils import generate_date_buckets


def search_nsf_grants(keyword: str, start_date: datetime, end_date: datetime) -> dict:
    """
    Search NSF grants by keyword and date range.
    
    Args:
        keyword: Search term (searches title and abstract)
        start_date: Start date for awards
        end_date: End date for awards
    
    Returns:
        dict with grant_count, total_amount, avg_amount, institutions
    """
    base_url = "https://www.research.gov/awardapi-service/v1/awards.json"
    
    params = {
        'keyword': keyword,
        'startDateStart': start_date.strftime('%m/%d/%Y'),
        'startDateEnd': end_date.strftime('%m/%d/%Y'),
        'printFields': 'id,title,startDate,expDate,fundsObligatedAmt,fundProgramName,agency,awardee',
        'offset': '1',
        'rpp': '500'  # Results per page (max 500)
    }
    
    try:
        response = requests.get(base_url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        # Extract results
        awards = data.get('response', {}).get('award', [])
        
        if not awards:
            return {
                'grant_count': 0,
                'total_amount': 0,
                'avg_amount': 0,
                'institutions': 0
            }
        
        # Calculate statistics
        total_amount = 0
        institutions = set()
        
        for award in awards:
            # Get funding amount
            amount_str = award.get('fundsObligatedAmt', '0')
            try:
                amount = float(amount_str.replace('$', '').replace(',', ''))
                total_amount += amount
            except (ValueError, AttributeError):
                pass
            
            # Track unique institutions
            awardee = award.get('awardee', '')
            if awardee:
                institutions.add(awardee)
        
        grant_count = len(awards)
        avg_amount = total_amount / grant_count if grant_count > 0 else 0
        
        return {
            'grant_count': grant_count,
            'total_amount': total_amount,
            'avg_amount': avg_amount,
            'institutions': len(institutions)
        }
    
    except requests.exceptions.RequestException as e:
        print(f"⚠️  NSF API error: {e}")
        return {
            'grant_count': 0,
            'total_amount': 0,
            'avg_amount': 0,
            'institutions': 0
        }


def get_range(
    search_term: str,
    start_year: int,
    end_year: int,
    bucket_days: int = 365
) -> pd.DataFrame:
    """
    Get NSF grant data over a time range with configurable bucketing.
    
    Args:
        search_term: Keyword to search for in grant titles/abstracts
        start_year: Start year
        end_year: End year
        bucket_days: Number of days per time bucket
    
    Returns:
        DataFrame with grant statistics per time period
    """
    """
    Get NSF grant data over a time range with configurable bucketing.
    
    Args:
        search_term: Keyword to search for in grant titles/abstracts
        start_year: Start year
        end_year: End year
        output_file: Path to output CSV file
        bucket_days: Number of days per time bucket
    
    Returns:
        DataFrame with grant statistics per time period
    """
    print(f"Searching NSF grants for '{search_term}' ({start_year}-{end_year}, {bucket_days}-day buckets)...")
    
    data = []
    
    for start_date, end_date, label in generate_date_buckets(start_year, end_year, bucket_days):
        print(f"  📅 {label}...", end=" ", flush=True)
        
        result = search_nsf_grants(search_term, start_date, end_date)
        
        row = {
            "period": label,
            "start_date": start_date.strftime("%Y-%m-%d"),
            "end_date": end_date.strftime("%Y-%m-%d"),
            "grant_count": result["grant_count"],
            "total_amount_usd": result["total_amount"],
            "avg_amount_usd": result["avg_amount"],
            "institutions": result["institutions"]
        }
        
        data.append(row)
        
        # Format amounts for display
        if result["grant_count"] > 0:
            total_m = result["total_amount"] / 1_000_000
            avg_k = result["avg_amount"] / 1_000
            print(f"✓ {result['grant_count']} grants, ${total_m:.1f}M total, ${avg_k:.0f}K avg, {result['institutions']} institutions")
        else:
            print("✓ No grants found")
        
        # Be respectful to the API
        time.sleep(1)
    
    # Return DataFrame (caller will save CSV)
    df = pd.DataFrame(data)
    return df


def visualize_data(
    csv_file: Path,
    search_term: str,
    output_dir: str,
    open_browser: bool = True,
    save_png: bool = False
) -> None:
    """
    Create visualizations for NSF grant data.
    
    Args:
        csv_file: Path to CSV file with grant data
        search_term: Search term used (for titles)
        output_dir: Directory to save visualizations
        open_browser: Whether to open HTML in browser
        save_png: Whether to save PNG images
    """
    try:
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots
    except ImportError:
        print("⚠️  Plotly not installed. Skipping visualization.")
        return
    
    # Read data
    df = pd.read_csv(csv_file)
    
    if df.empty:
        print("⚠️  No data to visualize")
        return
    
    # Create figure with secondary y-axis
    fig = make_subplots(
        rows=2, cols=1,
        subplot_titles=(
            f'NSF Grant Count for "{search_term}"',
            f'NSF Funding Amount for "{search_term}"'
        ),
        vertical_spacing=0.12,
        specs=[[{"secondary_y": False}], [{"secondary_y": True}]]
    )
    
    # Top chart: Grant count and institutions
    fig.add_trace(
        go.Bar(
            x=df['period'],
            y=df['grant_count'],
            name='Grant Count',
            marker_color='rgb(55, 83, 109)'
        ),
        row=1, col=1
    )
    
    # Bottom chart: Funding amounts
    fig.add_trace(
        go.Bar(
            x=df['period'],
            y=df['total_amount_usd'] / 1_000_000,  # Convert to millions
            name='Total Funding ($M)',
            marker_color='rgb(26, 118, 255)'
        ),
        row=2, col=1,
        secondary_y=False
    )
    
    fig.add_trace(
        go.Scatter(
            x=df['period'],
            y=df['avg_amount_usd'] / 1_000,  # Convert to thousands
            name='Avg Grant Size ($K)',
            mode='lines+markers',
            marker=dict(size=8, color='rgb(255, 127, 14)'),
            line=dict(width=3)
        ),
        row=2, col=1,
        secondary_y=True
    )
    
    # Update axes
    fig.update_xaxes(title_text="Time Period", row=2, col=1)
    fig.update_yaxes(title_text="Number of Grants", row=1, col=1)
    fig.update_yaxes(title_text="Total Funding ($ Millions)", row=2, col=1, secondary_y=False)
    fig.update_yaxes(title_text="Avg Grant Size ($ Thousands)", row=2, col=1, secondary_y=True)
    
    # Update layout
    fig.update_layout(
        height=800,
        showlegend=True,
        title_text=f"NSF Research Grants: {search_term}",
        hovermode='x unified'
    )
    
    # Save HTML
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    from utils.utils_io import slug
    term_slug = slug(search_term)
    html_file = output_path / f"{term_slug}_grants.html"
    
    fig.write_html(str(html_file))
    print(f"✅ Saved visualization: {html_file}")
    
    # Save PNG if requested
    if save_png:
        try:
            png_file = output_path / f"{term_slug}_grants.png"
            fig.write_image(str(png_file), width=1200, height=800)
            print(f"✅ Saved PNG: {png_file}")
        except Exception as e:
            print(f"⚠️  Could not save PNG: {e}")
    
    # Open in browser
    if open_browser:
        import webbrowser
        webbrowser.open(html_file.as_uri())


if __name__ == "__main__":
    # Test the module
    df = get_range("artificial intelligence", 2020, 2024, bucket_days=365)
    print("\n📊 Results:")
    print(df.to_string(index=False))
    
    # Save test CSV
    output_dir = Path("outputs/test_grants")
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_file = output_dir / "ai_grants_data.csv"
    df.to_csv(csv_file, index=False)
    
    # Create visualization
    visualize_data(csv_file, "artificial intelligence", str(output_dir), open_browser=False)
