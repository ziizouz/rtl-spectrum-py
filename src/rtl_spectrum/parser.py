"""CSV parser for rtl_power output data.

This module provides :class:`BinDataParser`, a stateful parser that
ingests raw CSV lines from ``rtl_power``, expands multi-dBm columns
into individual frequency bins, and merges/averages duplicate
frequency entries across multiple sweeps.
"""

from typing import Dict, List

from rtl_spectrum.models import BinData


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
        bins = self._convert_line(line)
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

    @staticmethod
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
