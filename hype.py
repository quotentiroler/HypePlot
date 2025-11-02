"""HypePlot: Track topic hype cycles

Usage:
  uv run hype "FHIR" 2015 2025 --source scholar,trends --format csv,html,png

Examples (PowerShell):
  # Get Scholar CSV only
  uv run hype "FHIR" 2015 2025 --source scholar --format csv
  
  # Full analysis with all outputs
  uv run hype "FHIR" 2015 2025 --source scholar,trends --format csv,html,png --topic
  
  # Trends only with visualization
  uv run hype "FHIR" 2015 2025 --source trends --format csv,html --topic
"""

from __future__ import annotations

import argparse
from pathlib import Path
from datetime import date, datetime, timedelta
import pandas as pd
import importlib

from utils.utils_io import resolve_effective_outdir, slug as util_slug, save_png_if_requested


def parse_year_or_date(value: str) -> int:
    """
    Parse a year (YYYY) or date (YYYY-MM-DD) string and return the year as an integer.
    
    Args:
        value: String in format "YYYY" or "YYYY-MM-DD"
    
    Returns:
        Year as integer
    
    Raises:
        ValueError: If the format is invalid
    """
    value = value.strip()
    
    # Try parsing as date first (YYYY-MM-DD)
    if '-' in value:
        try:
            parsed_date = datetime.strptime(value, "%Y-%m-%d")
            return parsed_date.year
        except ValueError:
            raise ValueError(f"Invalid date format: '{value}'. Expected YYYY-MM-DD")
    
    # Try parsing as year (YYYY)
    try:
        year = int(value)
        if year < 1900 or year > 2100:
            raise ValueError(f"Year {year} out of reasonable range (1900-2100)")
        return year
    except ValueError:
        raise ValueError(f"Invalid year/date: '{value}'. Expected YYYY or YYYY-MM-DD")


def get_available_sources() -> list[str]:
    """
    Dynamically discover available data sources from the sources/ directory.
    
    Returns:
        List of source names (without .py extension)
    """
    sources_dir = Path(__file__).parent / "sources"
    source_files = sources_dir.glob("*.py")
    
    # Exclude __init__.py and get just the module names
    sources = [
        f.stem for f in source_files 
        if f.stem != "__init__" and not f.stem.startswith("_")
    ]
    
    return sorted(sources)


def get_source_module(source_name: str):
    """
    Dynamically import a source module.
    
    Args:
        source_name: Name of the source module (e.g., 'scholar', 'trends')
    
    Returns:
        The imported module
    """
    return importlib.import_module(f"sources.{source_name}")


def process_generic_source(
    source_name: str,
    term: str,
    start_year: int,
    end_year: int,
    output_base: Path,
    term_slug: str,
    formats: list[str],
    results: dict,
    bucket_days: int,
    display_name: str | None = None,
    **get_range_kwargs
) -> None:
    """
    Generic handler for data sources that follow the standard pattern:
    - source_mod.get_range(term, start_year, end_year, bucket_days=..., **kwargs) -> DataFrame
    - source_mod.visualize_data(csv_file, term, output_dir, open_browser, save_png)
    
    Args:
        source_name: Source module name (e.g., 'github', 'arxiv')
        term: Search term
        start_year: Start year
        end_year: End year
        output_base: Base output directory
        term_slug: Slugified term for filenames
        formats: List of output formats
        results: Results dictionary to update
        bucket_days: Number of days per time bucket
        display_name: Display name for logging (defaults to source_name)
        **get_range_kwargs: Additional keyword arguments for get_range()
    """
    if display_name is None:
        display_name = source_name.capitalize()
    
    print(f"=== Fetching {display_name} data ===")
    source_mod = get_source_module(source_name)
    
    # Set up output location
    source_dir = output_base / source_name
    source_dir.mkdir(parents=True, exist_ok=True)
    source_csv = source_dir / f"{term_slug}_{source_name}_data.csv"
    
    # Fetch data with bucket_days parameter (returns DataFrame)
    df = source_mod.get_range(
        term, 
        start_year, 
        end_year, 
        bucket_days=bucket_days,
        **get_range_kwargs
    )
    
    # Save CSV using utility
    from utils.utils_io import save_csv
    save_csv(df, source_csv, display_name)
    
    if "csv" in formats:
        results[f'{source_name}_csv'] = source_csv
    
    # Visualize if html or png requested
    if "html" in formats or "png" in formats:
        print(f"=== Creating {display_name} visualizations ===")
        source_mod.visualize_data(
            str(source_csv),
            term,
            output_dir=str(source_dir),
            open_browser=False,
            save_png=("png" in formats)
        )
        if "html" in formats:
            results[f'{source_name}_html'] = source_dir / f"{term_slug}_{source_name}.html"
        if "png" in formats:
            results[f'{source_name}_png'] = source_dir / f"{term_slug}_{source_name}.png"
        print(f"✅ {display_name} charts saved to: {source_dir}/\n")



def run_hypeplot(
    term: str,
    start_year: int,
    end_year: int,
    sources: list[str],
    formats: list[str],
    topic: bool = False,
    no_open: bool = False,
    bucket: str = "yearly",
) -> int:
    """Main HypePlot workflow."""
    # Parse bucket specification
    bucket_days = None
    if bucket.startswith("days:"):
        try:
            bucket_days = int(bucket.split(":", 1)[1])
            if bucket_days <= 0:
                print(f"Error: bucket days must be positive, got {bucket_days}")
                return 1
        except (ValueError, IndexError):
            print(f"Error: Invalid bucket format '{bucket}'. Use 'days:N' where N is a positive integer.")
            return 1
    elif bucket == "yearly":
        bucket_days = 365  # Will be adjusted for leap years if needed
    elif bucket == "monthly":
        bucket_days = 30
    elif bucket == "quarterly":
        bucket_days = 90
    else:
        print(f"Error: Invalid bucket '{bucket}'. Use: yearly, monthly, quarterly, or days:N")
        return 1
    
    term_slug = util_slug(term)
    output_base = Path("outputs") / term_slug
    
    print(f"\n🔥 HypePlot: Analyzing '{term}' ({start_year}-{end_year})")
    print(f"   Sources: {', '.join(sources)}")
    print(f"   Formats: {', '.join(formats)}")
    print(f"   Bucket: {bucket} ({bucket_days} days)\n")
    
    results = {}
    
    # Process Scholar data (special handling - uses extract_scholar_data)
    if "scholar" in sources:
        print(f"=== Extracting Google Scholar publication counts ===")
        scholar_mod = get_source_module("scholar")
        
        # Set up organized output location
        scholar_dir = output_base / "scholar"
        scholar_dir.mkdir(parents=True, exist_ok=True)
        scholar_csv = scholar_dir / f"{term_slug}_scholar_data.csv"
        
        # Run scraper directly to organized location
        scholar_mod.extract_scholar_data(term, start_year, end_year, str(scholar_csv))
        
        if "csv" in formats:
            results['scholar_csv'] = scholar_csv
        print(f"✅ Scholar data saved to: {scholar_csv}\n")
        
        # Visualize if html or png requested
        if "html" in formats or "png" in formats:
            print(f"=== Creating Scholar visualizations ===")
            
            scholar_mod.visualize_data(
                str(scholar_csv),
                term,
                "line",
                None,
                outdir=str(scholar_dir),
                no_term_subdir=True,
                open_browser=False,
                save_png=("png" in formats),
            )
            
            if "html" in formats:
                results['scholar_html'] = scholar_dir / f"{term_slug}_line_chart.html"
            if "png" in formats:
                results['scholar_png'] = scholar_dir / f"{term_slug}_line_chart.png"
            print(f"✅ Scholar charts saved to: {scholar_dir}/\n")
    
    # Process Trends data (special handling - uses fetch_trends and annualize)
    if "trends" in sources:
        print(f"=== Fetching Google Trends data ===")
        trends_mod = get_source_module("trends")
        
        timeframe = "all"
        df_trends = trends_mod.fetch_trends(term, timeframe=timeframe, geo="", use_topic=topic, force=False)
        
        # Slice to last 10 years for annual
        today = date.today()
        try:
            start = today.replace(year=today.year - 10)
        except ValueError:
            start = today - timedelta(days=3650)
        df_trends = df_trends[(pd.to_datetime(df_trends["week"]) >= pd.to_datetime(start)) & (pd.to_datetime(df_trends["week"]) <= pd.to_datetime(today))]
        df_annual = trends_mod.annualize(df_trends)
        
        trends_dir = output_base / "trends"
        trends_dir.mkdir(parents=True, exist_ok=True)
        
        if "csv" in formats:
            trends_csv = trends_dir / f"trends_annual_{term_slug}.csv"
            df_annual.to_csv(trends_csv, index=False)
            results['trends_csv'] = trends_csv
            print(f"✅ Trends data saved to: {trends_csv}")
        
        # Visualize if html or png requested
        if "html" in formats or "png" in formats:
            print(f"=== Creating Trends visualizations ===")
            trends_html = trends_dir / f"trends_annual_{term_slug}.html"
            fig_trends = trends_mod.plot_trends_annual(
                df_annual,
                f"{term} (Worldwide, Topic)" if topic else f"{term} (Worldwide)",
                trends_html,
                open_browser=False
            )
            
            if "html" in formats:
                results['trends_html'] = trends_html
            if "png" in formats:
                save_png_if_requested(fig_trends, trends_html.with_suffix('.png'), True)
                results['trends_png'] = trends_html.with_suffix('.png')
            print(f"✅ Trends charts saved to: {trends_dir}/\n")
    
    # Process all other sources dynamically with generic handler
    # Get all available sources except the ones with special handling
    all_sources = get_available_sources()
    special_sources = {"scholar", "trends"}
    generic_source_names = [s for s in all_sources if s not in special_sources]
    
    # Display name mapping for better logging
    display_names = {
        "github": "GitHub repository",
        "arxiv": "arXiv preprint",
        "youtube": "YouTube video",
        "reddit": "Reddit discussion",
        "packages": "Package Registry",
        "news": "News Article",
        "jobs": "Job Postings",
        "twitter": "Twitter/X Mentions",
        "patents": "Patent Filing",
    }
    
    for source_name in generic_source_names:
        if source_name in sources:
            display_name = display_names.get(source_name, source_name.capitalize())
            
            # Special case for packages - needs registry parameter
            if source_name == "packages":
                process_generic_source(
                    source_name,
                    term,
                    start_year,
                    end_year,
                    output_base,
                    term_slug,
                    formats,
                    results,
                    bucket_days,
                    display_name,
                    registry="pypi"
                )
            else:
                process_generic_source(
                    source_name,
                    term,
                    start_year,
                    end_year,
                    output_base,
                    term_slug,
                    formats,
                    results,
                    bucket_days,
                    display_name
                )
    
    # Summary
    print(f"=== Summary ===")
    for key, path in results.items():
        print(f"  • {key}: {path}")
    print(f"\n🔥 HypePlot complete! Check {output_base}/ for results.")
    
    # Open first HTML file if requested
    if not no_open and "html" in formats:
        import webbrowser
        html_file = results.get('scholar_html') or results.get('trends_html')
        if html_file and Path(html_file).exists():
            webbrowser.open_new_tab(Path(html_file).resolve().as_uri())
    
    return 0


def build_parser() -> argparse.ArgumentParser:
    # Get available sources dynamically
    available_sources = get_available_sources()
    default_sources = ",".join(available_sources)  # Use all sources by default
    
    p = argparse.ArgumentParser(
        prog="hype",
        description="HypePlot - Track academic topic hype cycles",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # CSV only from Scholar (no visualizations)
  uv run hype "FHIR" 2015 2025 --source scholar
  
  # Full analysis with all visualizations
  uv run hype plot "FHIR" 2015 2025 --source scholar,trends --topic
  
  # Trends CSV only
  uv run hype "FHIR" 2015 2025 --source trends --topic
  
  # Custom format override
  uv run hype "FHIR" 2015 2025 --source scholar --format csv,html
        """
    )
    
    p.add_argument("term", help="Search term or topic to analyze")
    p.add_argument("start_year", help="Start year (YYYY) or date (YYYY-MM-DD) for analysis")
    p.add_argument("end_year", help="End year (YYYY) or date (YYYY-MM-DD) for analysis")
    
    p.add_argument(
        "plot",
        nargs="?",
        help="Add 'plot' to generate visualizations (html, png). Without 'plot', only CSV is generated."
    )
    
    p.add_argument(
        "--source",
        default=default_sources,
        help=(
            f"Data sources (comma-separated). Available: {', '.join(available_sources)}. "
            f"Default: {default_sources}"
        )
    )
    
    p.add_argument(
        "--format",
        default=None,
        help="Output formats (comma-separated): csv, html, png. Default: 'csv' without plot, 'csv,html,png' with plot"
    )
    
    p.add_argument(
        "--topic",
        action="store_true",
        help="Use Google Trends Topic mode for more accurate results"
    )
    
    p.add_argument(
        "--no-open",
        action="store_true",
        help="Don't open charts in browser automatically"
    )
    
    p.add_argument(
        "--bucket",
        default="yearly",
        help=(
            "Time bucket for data accumulation. Options: "
            "'yearly', 'monthly', 'quarterly' (3 months), "
            "or 'days:N' for custom day count (e.g., 'days:10', 'days:180'). "
            "Default: yearly"
        )
    )
    
    return p


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    
    # Parse start and end years (supports both YYYY and YYYY-MM-DD)
    try:
        start_year = parse_year_or_date(args.start_year)
        end_year = parse_year_or_date(args.end_year)
    except ValueError as e:
        print(f"Error: {e}")
        return 1
    
    # Check if "plot" was passed as positional argument
    has_plot = args.plot == "plot"
    
    # Set default format based on whether plot is requested
    if args.format is None:
        formats = ["csv", "html", "png"] if has_plot else ["csv"]
    else:
        formats = [f.strip() for f in args.format.split(",")]
    
    # Parse comma-separated sources
    sources = [s.strip() for s in args.source.split(",")]
    
    # Validate sources dynamically
    valid_sources = set(get_available_sources())
    invalid = set(sources) - valid_sources
    if invalid:
        print(f"Error: Invalid sources: {', '.join(invalid)}")
        print(f"Valid sources: {', '.join(sorted(valid_sources))}")
        return 1
    
    # Validate formats
    valid_formats = {"csv", "html", "png"}
    invalid = set(formats) - valid_formats
    if invalid:
        print(f"Error: Invalid formats: {', '.join(invalid)}")
        print(f"Valid formats: {', '.join(valid_formats)}")
        return 1
    
    return run_hypeplot(
        args.term,
        start_year,
        end_year,
        sources,
        formats,
        args.topic,
        args.no_open,
        args.bucket,
    )


if __name__ == "__main__":
    raise SystemExit(main())
