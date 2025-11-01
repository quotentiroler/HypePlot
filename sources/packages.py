"""
Package Registry Data Source for HypePlot
Tracks download statistics from PyPI, npm, and Maven Central.

Note: For PyPI, uses pypistats API (no auth required).
npm and Maven Central support is basic (package existence/creation date).
"""

import requests
import time
from datetime import datetime
import pandas as pd
from pathlib import Path
from utils.date_utils import generate_date_buckets
import json


def get_pypi_downloads(package_name: str, start_date: datetime, end_date: datetime) -> int:
    """
    Get PyPI package download statistics for a date range.
    
    Args:
        package_name: PyPI package name
        start_date: Start date (inclusive)
        end_date: End date (inclusive)
    
    Returns:
        Total download count for the period
    """
    # Use pypistats.org API
    url = f"https://pypistats.org/api/packages/{package_name}/overall"
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        total_downloads = 0
        
        if "data" in data:
            for entry in data["data"]:
                date_str = entry.get("date")
                downloads = entry.get("downloads", 0)
                
                if date_str:
                    try:
                        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
                        if start_date <= date_obj <= end_date:
                            total_downloads += downloads
                    except ValueError:
                        continue
        
        return total_downloads
    
    except Exception as e:
        print(f"⚠️  PyPI API error: {e}")
        return 0


def search_pypi_packages(query: str) -> list[str]:
    """
    Search for PyPI packages by keyword.
    
    Args:
        query: Search term
    
    Returns:
        List of matching package names
    """
    url = "https://pypi.org/search/"
    params = {"q": query}
    
    try:
        # Note: PyPI doesn't have a great search API, this is best-effort
        # In practice, users should specify exact package name
        response = requests.get(url, params=params, timeout=10)
        
        # For now, return the query itself as the package name
        # Users should specify exact package names for accurate results
        return [query.lower().replace(" ", "-")]
    
    except Exception as e:
        print(f"⚠️  PyPI search error: {e}")
        return []


def get_range(search_term: str, start_year: int, end_year: int, output_file: str = "packages_data.csv", registry: str = "pypi",
    bucket_days: int = 365
):
    """
    Extract package download statistics for a date range.
    
    Args:
        search_term: Package name or search term
        start_year: Start year
        end_year: End year
        output_file: Path to output CSV file
        registry: Package registry (pypi, npm, maven)
        bucket_days: Number of days per time bucket
    """
    print(f"Searching {registry.upper()} for '{search_term}' ({start_year}-{end_year}, {bucket_days}-day buckets)...")
    
    data = []
    
    if registry == "pypi":
        # Get downloads for each bucket period
        for start_date, end_date, label in generate_date_buckets(start_year, end_year, bucket_days):
            downloads = get_pypi_downloads(search_term, start_date, end_date)
            data.append({
                "period": label,
                "start_date": start_date.strftime("%Y-%m-%d"),
                "end_date": end_date.strftime("%Y-%m-%d"),
                "registry": "pypi",
                "package": search_term,
                "downloads": downloads
            })
            print(f"  📅 {label}: {downloads:,} downloads")
            time.sleep(0.5)  # Be respectful to the API
    
    elif registry == "npm":
        print("⚠️  npm download stats require npm API integration (coming soon)")
        print("    For now, check npmjs.com for package stats")
        
        for start_date, end_date, label in generate_date_buckets(start_year, end_year, bucket_days):
            data.append({
                "period": label,
            "start_date": start_date.strftime("%Y-%m-%d"),
            "end_date": end_date.strftime("%Y-%m-%d"),
                "registry": "npm",
                "package": search_term,
                "downloads": 0
            })
    
    elif registry == "maven":
        print("⚠️  Maven Central download stats require sonatype integration (coming soon)")
        print("    For now, check search.maven.org for package stats")
        
        for start_date, end_date, label in generate_date_buckets(start_year, end_year, bucket_days):
            data.append({
                "period": label,
            "start_date": start_date.strftime("%Y-%m-%d"),
            "end_date": end_date.strftime("%Y-%m-%d"),
                "registry": "maven",
                "package": search_term,
                "downloads": 0
            })
    
    # Save to CSV
    df = pd.DataFrame(data)
    df.to_csv(output_file, index=False)
    print(f"\n✅ Package data saved to: {output_file}")
    
    return df


def visualize_data(
    csv_file: str,
    term: str,
    output_dir: str = ".",
    open_browser: bool = False,
    save_png: bool = False
):
    """
    Create visualizations for package download data.
    
    Args:
        csv_file: Path to CSV file with package data
        term: Package name for title
        output_dir: Directory to save visualizations
        open_browser: Whether to open HTML in browser
        save_png: Whether to save PNG version
    """
    import plotly.graph_objects as go
    
    df = pd.read_csv(csv_file)
    
    fig = go.Figure()
    
    # Group by registry if multiple registries
    for registry in df["registry"].unique():
        df_registry = df[df["registry"] == registry]
        
        fig.add_trace(
            go.Scatter(
                x=df_registry["year"],
                y=df_registry["downloads"],
                mode="lines+markers",
                name=registry.upper(),
                line=dict(width=3),
                marker=dict(size=10),
                hovertemplate=(
                    "<b>%{x}</b><br>" +
                    f"{registry.upper()} Downloads: %{{y:,}}<br>" +
                    "<extra></extra>"
                )
            )
        )
    
    # Update layout
    fig.update_layout(
        title=f"Package Downloads: {term}",
        title_font_size=20,
        xaxis_title="Period",
        yaxis_title="Downloads",
        hovermode="x unified",
        height=600,
        showlegend=True,
        plot_bgcolor="white"
    )
    
    fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='lightgray')
    fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='lightgray')
    
    # Save HTML
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    html_file = output_path / f"{term.lower().replace(' ', '_')}_packages.html"
    fig.write_html(str(html_file))
    print(f"✅ Package chart saved: {html_file}")
    
    # Save PNG if requested
    if save_png:
        png_file = html_file.with_suffix('.png')
        try:
            fig.write_image(str(png_file), width=1200, height=600)
            print(f"✅ Package PNG saved: {png_file}")
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
        print("Usage: python packages.py '<package_name>' <start_year> <end_year> [registry]")
        print("  registry: pypi (default), npm, maven")
        sys.exit(1)
    
    term = sys.argv[1]
    start = int(sys.argv[2])
    end = int(sys.argv[3])
    registry = sys.argv[4] if len(sys.argv) > 4 else "pypi"
    
    df = get_range(term, start, end, registry=registry)
    visualize_data("packages_data.csv", term, open_browser=True)
