"""Data model for rtl_power spectral bin data.

This module defines the BinData dataclass, which represents a single
frequency bin with its measured power — the fundamental data unit
throughout the library.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class BinData:
    """A single frequency bin from rtl_power output.

    Holds both the raw CSV metadata (as strings, preserving the original
    format for round-trip fidelity) and computed numeric values used for
    analysis and plotting.

    Attributes:
        date: Date string from the CSV row (e.g. ``"2019-06-16"``).
        time: Time string from the CSV row (e.g. ``"23:10:56"``).
        frequency_start: String representation of the bin start frequency.
        frequency_start_parsed: Numeric start frequency in Hz.
        frequency_end: End-frequency / step string (mirrors Java quirk).
        bin_size: Bin width string in Hz (same value as ``frequency_end``).
        num_samples: Number-of-samples string from the CSV row.
        dbm_average: Computed average power in dBm.
        dbm_total: Running sum of dBm values for averaging.
        dbm_count: Number of dBm values accumulated.
    """

    date: str = ""
    time: str = ""
    frequency_start: str = ""
    frequency_start_parsed: int = 0
    frequency_end: str = ""
    bin_size: str = ""
    num_samples: str = ""
    dbm_average: float = 0.0
    dbm_total: float = 0.0
    dbm_count: int = 0

    def copy(self) -> "BinData":
        """Create a shallow copy of this BinData instance.

        Returns:
            A new BinData with the same field values.
        """
        return BinData(
            date=self.date,
            time=self.time,
            frequency_start=self.frequency_start,
            frequency_start_parsed=self.frequency_start_parsed,
            frequency_end=self.frequency_end,
            bin_size=self.bin_size,
            num_samples=self.num_samples,
            dbm_average=self.dbm_average,
            dbm_total=self.dbm_total,
            dbm_count=self.dbm_count,
        )
