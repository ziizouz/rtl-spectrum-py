"""Spectral analysis operations.

This module provides functions for manipulating spectral data,
primarily baseline subtraction (removing a reference/noise-floor
scan from a signal scan).
"""

from typing import Dict, List, Optional

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
