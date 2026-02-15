"""Spectral analysis operations.

This module provides functions for manipulating spectral data,
including baseline subtraction, peak-hold detection, and
min/max/average envelope computation across multiple sweeps.
"""

from typing import Dict, List, Tuple

from rtl_spectrum.models import BinData


def subtract(
    signal: List[BinData],
    baseline: List[BinData],
) -> List[BinData]:
    """Subtract baseline spectrum from signal spectrum.

    For each bin in *signal*, finds the matching frequency bin in
    *baseline* (by exact ``frequency_start`` string equality) and
    computes ``signal_dBm - baseline_dBm``.  Bins with no matching
    frequency in *baseline* are silently skipped.

    This mirrors the Java ``SubtractFile`` logic exactly.

    Args:
        signal: The measured signal data.
        baseline: The reference/noise-floor data to subtract.

    Returns:
        New list of :class:`BinData` containing the subtracted values.
        Only bins present in both *signal* and *baseline* are included.
    """
    # Build a lookup dict for O(1) matching
    baseline_map: Dict[str, BinData] = {
        b.frequency_start: b for b in baseline
    }

    result: List[BinData] = []
    for sig_bin in signal:
        base_bin = baseline_map.get(sig_bin.frequency_start)
        if base_bin is None:
            continue

        value = sig_bin.dbm_average - base_bin.dbm_average

        subtracted = sig_bin.copy()
        subtracted.dbm_average = value
        subtracted.dbm_total = value
        subtracted.dbm_count = 1
        result.append(subtracted)

    return result


def subtract_multi(
    signals: List[List[BinData]],
    baseline: List[BinData],
) -> List[List[BinData]]:
    """Subtract baseline from multiple signal series.

    Convenience wrapper that applies :func:`subtract` to each series
    in *signals*, matching the Java ``SubtractFile`` behaviour for
    multi-series chart data.

    Args:
        signals: List of signal series (each a list of :class:`BinData`).
        baseline: The baseline data to subtract from every series.

    Returns:
        List of subtracted series, one per input series.
    """
    return [subtract(series, baseline) for series in signals]


def peak_hold(
    sweeps: List[Tuple[str, List[BinData]]],
) -> List[BinData]:
    """Compute peak-hold spectrum across multiple sweeps.

    For each frequency bin present in *any* sweep, returns the
    maximum ``dbm_average`` value observed across all sweeps.
    Frequencies that do not appear in every sweep are still
    included — the maximum is computed only over sweeps where
    the bin is present (skip-missing strategy).

    Args:
        sweeps: List of ``(timestamp_label, bins)`` tuples as
            returned by :func:`~rtl_spectrum.io.load_csv_sweeps`.

    Returns:
        Sorted list of :class:`BinData` where ``dbm_average``
        holds the maximum power observed at that frequency.

    Raises:
        ValueError: If *sweeps* is empty.
    """
    if not sweeps:
        raise ValueError("Cannot compute peak hold on empty sweeps")

    # Track max dBm per frequency, keep a template BinData for metadata
    max_map: Dict[str, float] = {}
    template_map: Dict[str, BinData] = {}

    for _label, bins in sweeps:
        for b in bins:
            key = b.frequency_start
            if key not in max_map or b.dbm_average > max_map[key]:
                max_map[key] = b.dbm_average
                template_map[key] = b

    result: List[BinData] = []
    for key, max_val in max_map.items():
        entry = template_map[key].copy()
        entry.dbm_average = max_val
        entry.dbm_total = max_val
        entry.dbm_count = 1
        result.append(entry)

    result.sort(key=lambda b: b.frequency_start_parsed)
    return result


def envelope(
    sweeps: List[Tuple[str, List[BinData]]],
) -> Tuple[List[BinData], List[BinData], List[BinData]]:
    """Compute min/max/average envelope across multiple sweeps.

    For each frequency bin present in *any* sweep, computes the
    minimum, maximum, and arithmetic mean of ``dbm_average``
    values across all sweeps where that bin is present.

    Frequencies that do not appear in every sweep are still
    included — statistics are computed only over sweeps where
    the bin is present (skip-missing strategy).

    Args:
        sweeps: List of ``(timestamp_label, bins)`` tuples as
            returned by :func:`~rtl_spectrum.io.load_csv_sweeps`.

    Returns:
        A 3-tuple ``(min_series, max_series, avg_series)`` where
        each element is a sorted list of :class:`BinData`.  The
        ``dbm_average`` field holds the envelope value (min, max,
        or mean respectively).

    Raises:
        ValueError: If *sweeps* is empty.
    """
    if not sweeps:
        raise ValueError("Cannot compute envelope on empty sweeps")

    # Accumulate per-frequency statistics
    min_map: Dict[str, float] = {}
    max_map: Dict[str, float] = {}
    sum_map: Dict[str, float] = {}
    count_map: Dict[str, int] = {}
    template_map: Dict[str, BinData] = {}

    for _label, bins in sweeps:
        for b in bins:
            key = b.frequency_start
            val = b.dbm_average

            if key not in min_map:
                min_map[key] = val
                max_map[key] = val
                sum_map[key] = val
                count_map[key] = 1
                template_map[key] = b
            else:
                if val < min_map[key]:
                    min_map[key] = val
                if val > max_map[key]:
                    max_map[key] = val
                sum_map[key] += val
                count_map[key] += 1

    min_series: List[BinData] = []
    max_series: List[BinData] = []
    avg_series: List[BinData] = []

    for key in min_map:
        tmpl = template_map[key]

        min_entry = tmpl.copy()
        min_entry.dbm_average = min_map[key]
        min_entry.dbm_total = min_map[key]
        min_entry.dbm_count = 1
        min_series.append(min_entry)

        max_entry = tmpl.copy()
        max_entry.dbm_average = max_map[key]
        max_entry.dbm_total = max_map[key]
        max_entry.dbm_count = 1
        max_series.append(max_entry)

        avg_entry = tmpl.copy()
        avg_val = sum_map[key] / count_map[key]
        avg_entry.dbm_average = avg_val
        avg_entry.dbm_total = avg_val
        avg_entry.dbm_count = 1
        avg_series.append(avg_entry)

    min_series.sort(key=lambda b: b.frequency_start_parsed)
    max_series.sort(key=lambda b: b.frequency_start_parsed)
    avg_series.sort(key=lambda b: b.frequency_start_parsed)

    return min_series, max_series, avg_series
