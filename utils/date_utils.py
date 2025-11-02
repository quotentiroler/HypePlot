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
        bucket_days: Number of days per bucket (365 = calendar years, 90 = calendar quarters, 30 = calendar months)
    
    Yields:
        Tuples of (start_date, end_date, label) for each bucket
    """
    # Special handling for calendar years
    if bucket_days == 365 or bucket_days == 366:
        for year in range(start_year, end_year + 1):
            current_start = datetime(year, 1, 1)
            current_end = datetime(year, 12, 31, 23, 59, 59)
            label = str(year)
            yield current_start, current_end, label
        return
    
    # Special handling for calendar quarters
    if bucket_days == 90:
        quarter_starts = [
            (1, 1),   # Q1: Jan 1
            (4, 1),   # Q2: Apr 1
            (7, 1),   # Q3: Jul 1
            (10, 1),  # Q4: Oct 1
        ]
        quarter_ends = [
            (3, 31),  # Q1 ends Mar 31
            (6, 30),  # Q2 ends Jun 30
            (9, 30),  # Q3 ends Sep 30
            (12, 31), # Q4 ends Dec 31
        ]
        
        for year in range(start_year, end_year + 1):
            for q, ((start_m, start_d), (end_m, end_d)) in enumerate(zip(quarter_starts, quarter_ends), 1):
                current_start = datetime(year, start_m, start_d)
                current_end = datetime(year, end_m, end_d, 23, 59, 59)
                label = f"{year}-Q{q}"
                yield current_start, current_end, label
        return
    
    # Special handling for calendar months
    if bucket_days == 30:
        for year in range(start_year, end_year + 1):
            for month in range(1, 13):
                current_start = datetime(year, month, 1)
                # Last day of month
                if month == 12:
                    current_end = datetime(year, 12, 31, 23, 59, 59)
                else:
                    next_month = datetime(year, month + 1, 1)
                    current_end = next_month - timedelta(seconds=1)
                label = current_start.strftime("%Y-%m")
                yield current_start, current_end, label
        return
    
    # Custom buckets with fixed day count
    start_date = datetime(start_year, 1, 1)
    end_date = datetime(end_year, 12, 31, 23, 59, 59)
    
    current_start = start_date
    
    while current_start <= end_date:
        current_end = min(current_start + timedelta(days=bucket_days - 1, hours=23, minutes=59, seconds=59), end_date)
        
        # Custom buckets - use date range
        if current_end.year == current_start.year and current_end.month == current_start.month:
            label = current_start.strftime("%Y-%m-%d")
        else:
            label = f"{current_start.strftime('%Y-%m-%d')}_{current_end.strftime('%Y-%m-%d')}"
        
        yield current_start, current_end, label
        
        current_start = current_end + timedelta(seconds=1)


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
