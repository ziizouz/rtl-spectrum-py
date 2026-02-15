"""CSV parser for rtl_power output data.

This module provides :class:`BinDataParser`, a stateful parser that
ingests raw CSV lines from ``rtl_power``, expands multi-dBm columns
into individual frequency bins, and merges/averages duplicate
frequency entries across multiple sweeps.

It also provides :class:`SweepParser`, which preserves per-sweep
temporal information instead of averaging across all sweeps.
"""

from typing import Dict, List, Tuple

from rtl_spectrum.models import BinData


def _convert_line(line: str) -> Dict[str, BinData]:
    """Split a single CSV line into individual frequency bins.

    The rtl_power CSV format has columns:
    ``date, time, freq_start, freq_end, step, num_samples, dBm0[, dBm1, ...]``

    Columns 6+ each represent a sub-bin whose frequency is
    ``freq_start + i * step`` where *i* is the 0-based index
    within the dBm columns.  ``nan`` values are silently skipped.

    Args:
        line: A single CSV row string.

    Returns:
        Dict mapping frequency-start strings to :class:`BinData`
        instances.  Empty dict if the line has fewer than 7 columns.
    """
    parts = line.split(",")
    if len(parts) < 7:
        return {}

    date = parts[0].strip()
    time = parts[1].strip()
    frequency_start = int(parts[2].strip())
    step = float(parts[4].strip())

    result: Dict[str, BinData] = {}
    num_dbm_cols = len(parts) - 7 + 1  # columns 6..end

    for i in range(num_dbm_cols):
        raw_value = parts[6 + i].strip()
        try:
            value = float(raw_value)
        except ValueError:
            # Skip non-numeric values
            continue

        # Skip nan values (Python float("nan") doesn't raise,
        # but Java Double.valueOf("nan") throws NumberFormatException)
        if raw_value.lower() == "nan" or value != value:
            continue

        freq = int(frequency_start + i * step)
        freq_key = str(freq)

        cur = BinData(
            date=date,
            time=time,
            frequency_start_parsed=freq,
            frequency_start=freq_key,
            frequency_end=parts[4].strip(),
            bin_size=parts[4].strip(),
            num_samples=parts[5].strip(),
            dbm_total=value,
            dbm_count=1,
        )
        result[freq_key] = cur

    return result


class BinDataParser:
    """Stateful parser that accumulates rtl_power CSV lines.

    Each call to :meth:`add_line` parses one CSV row and merges
    its bins into an internal cache keyed by frequency-start string.
    Call :meth:`convert` to finalize and retrieve the sorted,
    averaged list of :class:`BinData`.

    Example:
        >>> parser = BinDataParser()
        >>> parser.add_line("2019-06-16,23:10:56,24000000,25000000,1000000.00,1,-24.14,-24.14")
        >>> data = parser.convert()
    """

    def __init__(self) -> None:
        """Initialize with an empty cache."""
        self._cache: Dict[str, BinData] = {}

    def add_line(self, line: str) -> None:
        """Parse a single CSV line and merge into the cache.

        Duplicate frequency keys have their dBm totals summed and
        counts incremented for later averaging.

        Args:
            line: A single CSV line from rtl_power output.
        """
        bins = _convert_line(line)
        for freq_key, bin_data in bins.items():
            existing = self._cache.get(freq_key)
            if existing is None:
                self._cache[freq_key] = bin_data
            else:
                existing.dbm_total += bin_data.dbm_total
                existing.dbm_count += bin_data.dbm_count

    def convert(self) -> List[BinData]:
        """Finalize parsing: sort by frequency and compute averages.

        Returns:
            Sorted list of :class:`BinData` with ``dbm_average`` set
            to ``dbm_total / dbm_count``.
        """
        result = sorted(self._cache.values(),
                        key=lambda b: b.frequency_start_parsed)
        for cur in result:
            cur.dbm_average = cur.dbm_total / cur.dbm_count
        return result


class SweepParser:
    """Stateful parser that groups rtl_power CSV lines by sweep.

    A new sweep is detected whenever the ``date + time`` timestamp
    string changes from the previous line.  Within each sweep,
    lines sharing the same frequency key are merged/averaged just
    like :class:`BinDataParser`.

    Call :meth:`add_line` for every CSV row, then :meth:`convert`
    to retrieve the list of sweeps in temporal order.

    Example:
        >>> parser = SweepParser()
        >>> parser.add_line("2019-06-16,23:10:56,24000000,25000000,1000000.00,1,-24.14,-24.14")
        >>> sweeps = parser.convert()
        >>> len(sweeps)
        1
    """

    def __init__(self) -> None:
        """Initialize with empty sweep state."""
        self._sweeps: List[Tuple[str, Dict[str, BinData]]] = []
        self._current_key: str = ""
        self._current_cache: Dict[str, BinData] = {}

    def add_line(self, line: str) -> None:
        """Parse a single CSV line and assign to the correct sweep.

        A new sweep boundary is detected when the ``date + time``
        timestamp of the current line differs from the previous
        line's timestamp.

        Args:
            line: A single CSV line from rtl_power output.
        """
        bins = _convert_line(line)
        if not bins:
            return

        # Determine the sweep key from the first bin's date+time
        sample = next(iter(bins.values()))
        sweep_key = f"{sample.date} {sample.time}"

        # Detect sweep boundary
        if sweep_key != self._current_key:
            if self._current_key:
                self._sweeps.append(
                    (self._current_key, self._current_cache)
                )
            self._current_key = sweep_key
            self._current_cache = {}

        # Merge bins into current sweep's cache
        for freq_key, bin_data in bins.items():
            existing = self._current_cache.get(freq_key)
            if existing is None:
                self._current_cache[freq_key] = bin_data
            else:
                existing.dbm_total += bin_data.dbm_total
                existing.dbm_count += bin_data.dbm_count

    def convert(self) -> List[Tuple[str, List[BinData]]]:
        """Finalize parsing: return sweeps in temporal order.

        Each sweep's bins are sorted by frequency and have their
        ``dbm_average`` computed from accumulated totals/counts.

        Returns:
            List of ``(timestamp_label, bins)`` tuples.  Each
            *timestamp_label* is a ``"date time"`` string and
            *bins* is a sorted list of :class:`BinData` with
            computed averages.
        """
        # Flush the last sweep
        all_sweeps = list(self._sweeps)
        if self._current_key:
            all_sweeps.append(
                (self._current_key, self._current_cache)
            )

        result: List[Tuple[str, List[BinData]]] = []
        for label, cache in all_sweeps:
            bins = sorted(cache.values(),
                          key=lambda b: b.frequency_start_parsed)
            for cur in bins:
                cur.dbm_average = cur.dbm_total / cur.dbm_count
            result.append((label, bins))

        return result
