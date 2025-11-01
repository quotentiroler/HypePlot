"""Date bucketing utilities for HypePlot.

Provides shared logic for aggregating data by time periods (yearly, monthly, custom days, etc.)
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Iterator


def generate_date_buckets(
    start_year: int,
    end_year: int,
    bucket_days: int
) -> Iterator[tuple[datetime, datetime, str]]:
    """
    Generate date buckets for data aggregation.
    
    Args:
        start_year: Start year (inclusive)
        end_year: End year (inclusive)
        bucket_days: Number of days per bucket
    
    Yields:
        Tuples of (start_date, end_date, label) for each bucket
    """
    start_date = datetime(start_year, 1, 1)
    end_date = datetime(end_year, 12, 31, 23, 59, 59)
    
    current_start = start_date
    bucket_num = 1
    
    while current_start <= end_date:
        current_end = min(current_start + timedelta(days=bucket_days - 1, hours=23, minutes=59, seconds=59), end_date)
        
        # Generate label based on bucket size
        if bucket_days == 365 or bucket_days == 366:
            # Yearly buckets - just use the year
            label = str(current_start.year)
        elif bucket_days == 30:
            # Monthly buckets - use YYYY-MM
            label = current_start.strftime("%Y-%m")
        elif bucket_days == 90:
            # Quarterly buckets - use YYYY-Q#
            quarter = (current_start.month - 1) // 3 + 1
            label = f"{current_start.year}-Q{quarter}"
        else:
            # Custom buckets - use date range
            if current_end.year == current_start.year and current_end.month == current_start.month:
                label = current_start.strftime("%Y-%m-%d")
            else:
                label = f"{current_start.strftime('%Y-%m-%d')}_{current_end.strftime('%Y-%m-%d')}"
        
        yield current_start, current_end, label
        
        current_start = current_end + timedelta(seconds=1)
        bucket_num += 1


def format_bucket_label(start: datetime, end: datetime, bucket_days: int) -> str:
    """
    Format a bucket label based on the bucket size.
    
    Args:
        start: Bucket start date
        end: Bucket end date
        bucket_days: Number of days in bucket
    
    Returns:
        Formatted label string
    """
    if bucket_days == 365 or bucket_days == 366:
        return str(start.year)
    elif bucket_days == 30:
        return start.strftime("%Y-%m")
    elif bucket_days == 90:
        quarter = (start.month - 1) // 3 + 1
        return f"{start.year}-Q{quarter}"
    else:
        if end.year == start.year and end.month == start.month:
            return start.strftime("%Y-%m-%d")
        else:
            return f"{start.strftime('%Y-%m-%d')}_{end.strftime('%Y-%m-%d')}"


def year_to_bucket_count(start_year: int, end_year: int, bucket_days: int) -> int:
    """
    Calculate how many buckets will be generated for a given year range.
    
    Args:
        start_year: Start year (inclusive)
        end_year: End year (inclusive)
        bucket_days: Number of days per bucket
    
    Returns:
        Number of buckets
    """
    start_date = datetime(start_year, 1, 1)
    end_date = datetime(end_year, 12, 31)
    total_days = (end_date - start_date).days + 1
    
    return (total_days + bucket_days - 1) // bucket_days  # Ceiling division
