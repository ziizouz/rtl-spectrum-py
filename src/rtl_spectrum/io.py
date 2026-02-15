"""File I/O for rtl_power CSV data.

This module provides functions to load rtl_power CSV files into
:class:`~rtl_spectrum.models.BinData` lists and to export processed
data back to rtl_power-compatible CSV format.
"""

from pathlib import Path
from typing import List, Tuple, Union

from rtl_spectrum.models import BinData
from rtl_spectrum.parser import BinDataParser, SweepParser


def load_csv(path: Union[str, Path]) -> List[BinData]:
    """Load an rtl_power CSV file and return parsed bin data.

    Reads the file line-by-line, feeding each line into a
    :class:`~rtl_spectrum.parser.BinDataParser`, then finalizes
    with averaging and sorting.

    Args:
        path: Path to the CSV file.

    Returns:
        Sorted list of :class:`~rtl_spectrum.models.BinData` with
        computed averages.

    Raises:
        FileNotFoundError: If *path* does not exist.
        IOError: If the file cannot be read.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"CSV file not found: {path}")

    parser = BinDataParser()
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.rstrip("\n\r")
            if line:
                parser.add_line(line)
    return parser.convert()


def load_csv_sweeps(
    path: Union[str, Path],
) -> List[Tuple[str, List[BinData]]]:
    """Load an rtl_power CSV file preserving per-sweep temporal data.

    Unlike :func:`load_csv`, this function keeps each sweep separate
    instead of averaging across all sweeps.  A new sweep boundary is
    detected whenever the ``date + time`` timestamp changes between
    consecutive CSV rows.

    Args:
        path: Path to the CSV file.

    Returns:
        List of ``(timestamp_label, bins)`` tuples in temporal order.
        Each *timestamp_label* is a ``"date time"`` string (e.g.
        ``"2026-02-15 12:29:54"``) and *bins* is a sorted list of
        :class:`~rtl_spectrum.models.BinData` with computed averages.

    Raises:
        FileNotFoundError: If *path* does not exist.
        IOError: If the file cannot be read.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"CSV file not found: {path}")

    parser = SweepParser()
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.rstrip("\n\r")
            if line:
                parser.add_line(line)
    return parser.convert()


def save_csv(data: List[BinData], path: Union[str, Path]) -> None:
    """Save bin data to an rtl_power-compatible CSV file.

    Writes one row per :class:`~rtl_spectrum.models.BinData` in the
    7-column format:
    ``date,time,frequencyStart,frequencyEnd,binSize,numSamples,dbmAverage``

    This matches the Java ``SaveTask`` output format exactly.

    Args:
        data: List of :class:`~rtl_spectrum.models.BinData` to write.
        path: Destination file path.

    Raises:
        IOError: If the file cannot be written.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as fh:
        for cur in data:
            fh.write(
                f"{cur.date},{cur.time},{cur.frequency_start},"
                f"{cur.frequency_end},{cur.bin_size},"
                f"{cur.num_samples},{cur.dbm_average}\n"
            )
