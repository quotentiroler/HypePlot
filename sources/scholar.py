"""Scholar/CSV visualization tool

Generic Plotly visualizations for yearly CSVs. Accepts:
- Scholar-style CSVs: columns [year, results]
- Google Trends annual CSVs: columns [year, interest] (auto-mapped to results)

Features:
- --outdir with per-term subfolder by default (disable with --no-term-subdir)
- --png to export static PNGs (requires kaleido)
- --no-open to suppress auto-opening charts
"""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import sys
import os
from pathlib import Path
from utils.utils_io import slug as util_slug, resolve_effective_outdir, save_png_if_requested
from utils import extract_occurrences


def extract_scholar_data(search_term: str, start_year: int, end_year: int, output_file: str):
    """
    Extract Google Scholar publication counts using extract_occurrences utility.
    
    Args:
        search_term: Term to search for
        start_year: Start year
        end_year: End year
        output_file: Path to output CSV file
    """
    extract_occurrences.get_range(search_term, start_year, end_year, output_file)


def load_data(csv_file, example_target_dir: Path | None = None) -> tuple[pd.DataFrame, str]:
    """Load data from CSV file. Creates example data if file doesn't exist.

    If example_target_dir is provided and csv_file is missing, the example CSV
    will be created under example_target_dir using the provided filename.
    """
    path = Path(csv_file)
    if not path.exists():
        # Create example data
        print(f"⚠️  File '{csv_file}' not found. Creating example FHIR data...")
        example_data = """year,results
2015,274
2016,507
2017,663
2018,909
2019,1210
2020,1470
2021,2070
2022,1770
2023,2270
2024,2710
2025,3640"""
        if example_target_dir is not None:
            example_target_dir.mkdir(parents=True, exist_ok=True)
            path = example_target_dir / path.name
        with open(path, 'w') as f:
            f.write(example_data)
        print(f"✅ Created '{path}' with example data")
    
    df = pd.read_csv(path)
    # Normalize common schemas: accept either 'results' or 'interest' (from Trends annual CSV)
    lower_cols = {c.lower(): c for c in df.columns}
    source_kind = "results"
    # If 'results' missing but 'interest' present, treat 'interest' as 'results'
    if "results" not in lower_cols and "interest" in lower_cols:
        df = df.rename(columns={lower_cols["interest"]: "results"})
        source_kind = "interest"
    return df, source_kind


def create_line_chart(df, search_term, output_file=None, open_browser=True, save_png=False, y_axis_title: str = "Number of Results"):
    """Create an interactive line chart using Plotly with detailed statistics."""
    
    # Calculate year-over-year change
    df = df.copy()
    df['yoy_change'] = df['results'].diff()
    df['yoy_pct_change'] = df['results'].pct_change() * 100
    
    # Create custom hover text with all details
    hover_text = []
    for idx, row in df.iterrows():
        if pd.isna(row['yoy_change']):
            hover_text.append(
                f"<b>Year:</b> {int(row['year'])}<br>"
                f"<b>Results:</b> {int(row['results']):,}<br>"
                f"<b>Change:</b> N/A (first year)"
            )
        else:
            change_symbol = "📈" if row['yoy_change'] > 0 else "📉" if row['yoy_change'] < 0 else "➡️"
            hover_text.append(
                f"<b>Year:</b> {int(row['year'])}<br>"
                f"<b>Results:</b> {int(row['results']):,}<br>"
                f"<b>Change:</b> {change_symbol} {int(row['yoy_change']):+,} ({row['yoy_pct_change']:+.1f}%)<br>"
                f"<b>Prev Year:</b> {int(df.loc[idx-1, 'results']):,}"
            )
    
    # Calculate statistics
    total_growth = ((df['results'].iloc[-1] / df['results'].iloc[0]) - 1) * 100
    avg_annual_growth = df['yoy_pct_change'].mean()
    max_year = df.loc[df['results'].idxmax(), 'year']
    max_value = df['results'].max()
    
    fig = go.Figure()
    
    # Add line trace
    fig.add_trace(go.Scatter(
        x=df['year'],
        y=df['results'],
        mode='lines+markers',
        name='Results',
        line=dict(color='#1f77b4', width=3),
        marker=dict(size=10, color='#1f77b4', line=dict(width=2, color='white')),
        hovertemplate='%{text}<extra></extra>',
        text=hover_text
    ))
    
    # Annotate the peak
    fig.add_annotation(
        x=max_year,
        y=max_value,
        text=f"Peak: {int(max_value):,}",
        showarrow=True,
        arrowhead=2,
        arrowsize=1,
        arrowwidth=2,
        arrowcolor="#d62728",
        ax=0,
        ay=-40,
        font=dict(size=11, color="#d62728"),
        bgcolor="white",
        bordercolor="#d62728",
        borderwidth=2
    )
    
    # Create subtitle with statistics
    subtitle = (
        f"Total Growth: {total_growth:+.1f}% | "
        f"Avg Annual Growth: {avg_annual_growth:+.1f}% | "
        f"Peak: {int(max_value):,} ({int(max_year)})"
    )
    
    # Customize the layout
    fig.update_layout(
        title=dict(
            text=f'<b>Academic Keyword Occurrence: "{search_term}"</b><br><sub>{subtitle}</sub>',
            font=dict(size=18)
        ),
        xaxis_title="Year",
    yaxis_title=y_axis_title,
        hovermode='closest',
        template='plotly_white',
        font=dict(size=12),
        xaxis=dict(
            showgrid=True,
            gridwidth=1,
            gridcolor='LightGray',
            dtick=1
        ),
        yaxis=dict(
            showgrid=True,
            gridwidth=1,
            gridcolor='LightGray'
        ),
        height=600,
        showlegend=False
    )
    
    if output_file:
        fig.write_html(output_file)
        print(f"Chart saved to: {output_file}")
        save_png_if_requested(fig, Path(output_file).with_suffix('.png'), save_png)
    
    if open_browser:
        fig.show()
    return fig


def create_bar_chart(df, search_term, output_file=None, open_browser=True, save_png=False, y_axis_title: str = "Number of Results"):
    """Create an interactive bar chart using Plotly with growth indicators."""
    
    df = df.copy()
    df['yoy_pct_change'] = df['results'].pct_change() * 100
    
    # Color bars based on growth (green for positive, red for negative)
    colors = ['#2ca02c' if pd.isna(change) or change >= 0 else '#d62728' 
              for change in df['yoy_pct_change']]
    
    # Create hover text
    hover_text = []
    for idx, row in df.iterrows():
        if pd.isna(row['yoy_pct_change']):
            hover_text.append(
                f"<b>{int(row['year'])}</b><br>"
                f"Results: {int(row['results']):,}<br>"
                f"Change: N/A"
            )
        else:
            hover_text.append(
                f"<b>{int(row['year'])}</b><br>"
                f"Results: {int(row['results']):,}<br>"
                f"Growth: {row['yoy_pct_change']:+.1f}%"
            )
    
    # Calculate statistics
    total_growth = ((df['results'].iloc[-1] / df['results'].iloc[0]) - 1) * 100
    avg_value = df['results'].mean()
    
    subtitle = f"Total Growth: {total_growth:+.1f}% | Average: {int(avg_value):,} results/year"
    
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        x=df['year'],
        y=df['results'],
        marker_color=colors,
        text=[f"{int(x):,}" for x in df['results']],
        textposition='outside',
        hovertemplate='%{text}<extra></extra>',
        hovertext=hover_text
    ))
    
    # Customize the layout
    fig.update_layout(
        title=dict(
            text=f'<b>Academic Keyword Occurrence: "{search_term}"</b><br><sub>{subtitle}</sub>',
            font=dict(size=18)
        ),
        xaxis_title="Year",
    yaxis_title=y_axis_title,
        template='plotly_white',
        font=dict(size=12),
        xaxis=dict(
            showgrid=False,
            dtick=1
        ),
        yaxis=dict(
            showgrid=True,
            gridwidth=1,
            gridcolor='LightGray'
        ),
        height=600
    )
    
    if output_file:
        fig.write_html(output_file)
        print(f"Chart saved to: {output_file}")
        save_png_if_requested(fig, Path(output_file).with_suffix('.png'), save_png)
    
    if open_browser:
        fig.show()
    return fig


def create_area_chart(df, search_term, output_file=None, open_browser=True, save_png=False, y_axis_title: str = "Number of Results"):
    """Create an interactive area chart using Plotly."""
    
    fig = px.area(
        df,
        x='year',
        y='results',
        title=f'Academic Keyword Occurrence: "{search_term}"',
        labels={'year': 'Year', 'results': 'Number of Results'}
    )
    
    # Customize the layout
    fig.update_layout(
        hovermode='x unified',
        template='plotly_white',
        font=dict(size=12),
        title_font_size=16,
        xaxis=dict(
            showgrid=True,
            gridwidth=1,
            gridcolor='LightGray',
            dtick=1
        ),
        yaxis=dict(
            showgrid=True,
            gridwidth=1,
            gridcolor='LightGray'
        )
    )
    
    # Customize the area
    fig.update_traces(
        fillcolor='rgba(31, 119, 180, 0.3)',
        line=dict(color='#1f77b4', width=2)
    )
    
    if output_file:
        fig.write_html(output_file)
        print(f"Chart saved to: {output_file}")
        save_png_if_requested(fig, Path(output_file).with_suffix('.png'), save_png)
    
    if open_browser:
        fig.show()
    return fig


def create_growth_chart(df, search_term, output_file=None, open_browser=True, save_png=False):
    """Create a detailed chart showing year-over-year growth rate with statistics."""
    
    # Calculate growth rate
    df = df.copy()
    df['growth_rate'] = df['results'].pct_change() * 100
    df['absolute_change'] = df['results'].diff()
    
    # Skip first year (no previous data)
    df_growth = df[1:].copy()
    
    # Calculate statistics
    avg_growth = df_growth['growth_rate'].mean()
    max_growth_idx = df_growth['growth_rate'].idxmax()
    max_growth_year = df.loc[max_growth_idx, 'year']
    max_growth_val = df.loc[max_growth_idx, 'growth_rate']
    
    min_growth_idx = df_growth['growth_rate'].idxmin()
    min_growth_year = df.loc[min_growth_idx, 'year']
    min_growth_val = df.loc[min_growth_idx, 'growth_rate']
    
    fig = go.Figure()
    
    # Create custom hover text
    hover_text = []
    for idx, row in df_growth.iterrows():
        prev_year = int(row['year']) - 1
        prev_val = df.loc[idx-1, 'results']
        hover_text.append(
            f"<b>{int(row['year'])}</b><br>"
            f"Growth: {row['growth_rate']:+.1f}%<br>"
            f"Change: {int(row['absolute_change']):+,}<br>"
            f"{prev_year}: {int(prev_val):,} → {int(row['results']):,}"
        )
    
    # Add bar chart for growth rate
    colors = ['#2ca02c' if x > 0 else '#d62728' if x < 0 else 'gray' 
              for x in df_growth['growth_rate']]
    
    fig.add_trace(go.Bar(
        x=df_growth['year'],
        y=df_growth['growth_rate'],
        marker_color=colors,
        text=[f"{x:+.1f}%" for x in df_growth['growth_rate']],
        textposition='outside',
        hovertemplate='%{text}<extra></extra>',
        hovertext=hover_text
    ))
    
    # Add average line
    fig.add_hline(
        y=avg_growth,
        line_dash="dash",
        line_color="blue",
        annotation_text=f"Average: {avg_growth:+.1f}%",
        annotation_position="right"
    )
    
    # Annotate max growth
    fig.add_annotation(
        x=max_growth_year,
        y=max_growth_val,
        text=f"Highest: {max_growth_val:+.1f}%",
        showarrow=True,
        arrowhead=2,
        arrowcolor="green",
        ax=0,
        ay=-40 if max_growth_val > 0 else 40,
        font=dict(color="green", size=11),
        bgcolor="white",
        bordercolor="green",
        borderwidth=2
    )
    
    # Annotate min growth if it's negative
    if min_growth_val < 0:
        fig.add_annotation(
            x=min_growth_year,
            y=min_growth_val,
            text=f"Lowest: {min_growth_val:.1f}%",
            showarrow=True,
            arrowhead=2,
            arrowcolor="red",
            ax=0,
            ay=40,
            font=dict(color="red", size=11),
            bgcolor="white",
            bordercolor="red",
            borderwidth=2
        )
    
    subtitle = (
        f"Average Growth: {avg_growth:+.1f}% | "
        f"Best Year: {int(max_growth_year)} ({max_growth_val:+.1f}%)"
    )
    
    # Customize the layout
    fig.update_layout(
        title=dict(
            text=f'<b>Year-over-Year Growth Rate: "{search_term}"</b><br><sub>{subtitle}</sub>',
            font=dict(size=18)
        ),
        xaxis_title='Year',
        yaxis_title='Growth Rate (%)',
        template='plotly_white',
        font=dict(size=12),
        xaxis=dict(dtick=1),
        yaxis=dict(
            showgrid=True,
            gridwidth=1,
            gridcolor='LightGray',
            zeroline=True,
            zerolinewidth=2,
            zerolinecolor='black'
        ),
        height=600
    )
    
    if output_file:
        fig.write_html(output_file)
        print(f"Chart saved to: {output_file}")
        save_png_if_requested(fig, Path(output_file).with_suffix('.png'), save_png)
    
    if open_browser:
        fig.show()
    return fig


def visualize_data(csv_file, search_term, chart_type='line', output_file=None, outdir=None, no_term_subdir=False, open_browser=True, save_png=False):
    """
    Visualize data from CSV file.
    """
    # Resolve effective output directory (optional)
    effective_outdir = resolve_effective_outdir(outdir, search_term, no_term_subdir=no_term_subdir)
    # If the CSV doesn't exist and the user passed a bare filename, create the example under effective_outdir
    example_dir = None
    if not os.path.exists(csv_file) and (outdir is not None) and (os.path.dirname(csv_file) in ("", ".")):
        example_dir = Path(effective_outdir) if effective_outdir is not None else None
    df, source_kind = load_data(csv_file, example_target_dir=example_dir)
    # Ensure sorted by year ascending if present
    if 'year' in df.columns:
        df = df.sort_values('year').reset_index(drop=True)
    # Auto-generate output filename if not provided
    if output_file is None:
        safe_term = search_term.replace('"', '').replace("'", "").replace(" ", "_").lower()
        output_file = f"{safe_term}_{chart_type}_chart.html"
    # If an outdir is provided and output_file is a filename (no path), write under effective_outdir
    if effective_outdir is not None and output_file and not os.path.isabs(output_file) and os.path.dirname(output_file) in ("", "."):
        output_file = str(Path(effective_outdir) / output_file)
    
    # Choose y-axis label based on source
    y_axis_title = "Number of Results" if source_kind == "results" else "Avg Search Interest (0-100)"
    if chart_type == 'line':
        fig = create_line_chart(df, search_term, output_file, open_browser=open_browser, save_png=save_png, y_axis_title=y_axis_title)
    elif chart_type == 'bar':
        fig = create_bar_chart(df, search_term, output_file, open_browser=open_browser, save_png=save_png, y_axis_title=y_axis_title)
    elif chart_type == 'area':
        fig = create_area_chart(df, search_term, output_file, open_browser=open_browser, save_png=save_png, y_axis_title=y_axis_title)
    elif chart_type == 'growth':
        fig = create_growth_chart(df, search_term, output_file, open_browser=open_browser, save_png=save_png)
    else:
        raise ValueError(f"Unknown chart type: {chart_type}. Use: line, bar, area, or growth")

    # Save normalized data alongside chart for traceability when outdir is used
    if effective_outdir is not None:
        safe_term = search_term.replace('"', '').replace("'", "").replace(" ", "_").lower()
        data_csv = Path(effective_outdir) / f"{safe_term}_scholar_data.csv"
        df_to_save = df.copy()
        df_to_save['source'] = source_kind
        try:
            df_to_save.to_csv(data_csv, index=False)
            print(f"Saved data used for chart to: {data_csv}")
        except Exception:
            pass
    
    return fig


def main():
    if len(sys.argv) < 3:
        print("Usage: uv run python scholar.py <csv_file> '<search_term>' [chart_type] [output_file] [--outdir=<path>] [--category=<name>] [--no-term-subdir] [--png] [--no-open]")
        print("\nChart types: line (default), bar, area, growth")
        print("\nExamples (PowerShell):")
        print("  uv run python scholar.py fhir_complete.csv 'FHIR' line --category=scholar  # saves under outputs/fhir/scholar/")
        print("  uv run python scholar.py fhir_complete.csv 'FHIR' growth --outdir=outputs/fhir/scholar --png --no-open")
        return
    args = sys.argv[1:]
    # Flags
    outdir_arg = next((a.split("=",1)[1] for a in args if a.startswith("--outdir=")), None)
    category_arg = next((a.split("=",1)[1] for a in args if a.startswith("--category=")), None)
    no_term_subdir = any(a == "--no-term-subdir" for a in args)
    save_png = any(a == "--png" for a in args)
    no_open = any(a == "--no-open" for a in args)
    # Positionals (strip flags)
    pos = [a for a in args if not a.startswith("--")]
    csv_file = pos[0]
    search_term = pos[1]
    chart_type = pos[2] if len(pos) > 2 else 'line'
    output_file = pos[3] if len(pos) > 3 else None
    
    # If --outdir is not provided but a --category is, default to outputs/<term_slug>/<category>
    local_no_term_subdir = no_term_subdir
    if outdir_arg is None and category_arg:
        term_slug = util_slug(search_term)
        outdir_arg = str(Path("outputs") / term_slug / category_arg)
        # We already included the term in outdir; prevent resolve_effective_outdir from adding it again
        local_no_term_subdir = True
    visualize_data(
        csv_file,
        search_term,
        chart_type,
        output_file,
        outdir=outdir_arg,
        no_term_subdir=local_no_term_subdir,
        open_browser=(not no_open),
        save_png=save_png,
    )


if __name__ == "__main__":
    main()