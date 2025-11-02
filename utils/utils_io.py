"""Shared utilities for output directories, slugging, and optional PNG export."""
from __future__ import annotations

from pathlib import Path
import webbrowser
import pandas as pd


def slug(s: str) -> str:
    """Create a filesystem-friendly slug from a term."""
    return s.replace("\\", "").replace("/", "").replace(" ", "_").lower()


def save_csv(df: pd.DataFrame, output_file: str | Path, source_name: str = "Data") -> Path:
    """
    Save a DataFrame to CSV with consistent formatting and messaging.
    
    Args:
        df: DataFrame to save
        output_file: Path where to save the CSV
        source_name: Display name for logging (e.g., "GitHub", "NSF grants")
    
    Returns:
        Path object of the saved file
    """
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    print(f"✅ {source_name} data saved to: {output_path}")
    return output_path


def resolve_effective_outdir(outdir_arg: str | None, term: str, no_term_subdir: bool = False) -> Path | None:
    """Resolve and create the output directory.

    If outdir_arg is provided, create it and by default create a per-term subdirectory
    unless no_term_subdir is True. Returns the effective directory path or None.
    """
    if not outdir_arg:
        return None
    base = Path(outdir_arg)
    effective = base / slug(term) if not no_term_subdir else base
    effective.mkdir(parents=True, exist_ok=True)
    return effective


def maybe_open_in_browser(path: Path, open_browser: bool = True) -> None:
    if not open_browser:
        return
    try:
        webbrowser.open_new_tab(Path(path).resolve().as_uri())
    except Exception:
        pass


def save_png_if_requested(fig, path: Path, save_png: bool) -> None:
    """Save a PNG for a plotly figure if requested (requires kaleido)."""
    if not save_png:
        return
    try:
        png_path = path if path.suffix.lower() == ".png" else path.with_suffix(".png")
        fig.write_image(str(png_path))
        print(f"Saved PNG snapshot to: {png_path}")
    except Exception as e:
        print(
            "Note: PNG export skipped (install 'kaleido' to enable). Error: \n"  # newline for readability
            "Image export using the \"kaleido\" engine requires the Kaleido package,\n"
            "which can be installed using pip:\n\n"
            "    $ pip install --upgrade kaleido\n"
        )
