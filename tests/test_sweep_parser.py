"""Tests for SweepParser and load_csv_sweeps."""

from pathlib import Path

import pytest

from rtl_spectrum.io import load_csv_sweeps
from rtl_spectrum.parser import SweepParser


class TestSweepParser:
    """Tests for the SweepParser class."""

    def test_single_line(self):
        """A single CSV line produces one sweep with parsed bins."""
        parser = SweepParser()
        parser.add_line(
            "2019-06-16,23:10:56,24000000,25000000,1000000.00,1,-24.14,-24.14"
        )
        sweeps = parser.convert()

        assert len(sweeps) == 1
        label, bins = sweeps[0]
        assert label == "2019-06-16 23:10:56"
        assert len(bins) == 2
        assert bins[0].frequency_start_parsed == 24000000
        assert bins[1].frequency_start_parsed == 25000000

    def test_empty_input(self):
        """No lines added produces an empty sweep list."""
        parser = SweepParser()
        sweeps = parser.convert()
        assert sweeps == []

    def test_short_line_skipped(self):
        """Lines with fewer than 7 columns are ignored."""
        parser = SweepParser()
        parser.add_line("too,few,columns")
        sweeps = parser.convert()
        assert sweeps == []

    def test_two_sweeps_detected(self):
        """Different timestamps produce separate sweeps."""
        parser = SweepParser()
        parser.add_line(
            "2019-06-16,10:00:00,100000000,101000000,1000000.00,1,-10.0"
        )
        parser.add_line(
            "2019-06-16,10:00:00,101000000,102000000,1000000.00,1,-11.0"
        )
        # Second sweep — time changes
        parser.add_line(
            "2019-06-16,10:01:00,100000000,101000000,1000000.00,1,-12.0"
        )
        parser.add_line(
            "2019-06-16,10:01:00,101000000,102000000,1000000.00,1,-13.0"
        )

        sweeps = parser.convert()
        assert len(sweeps) == 2

        label1, bins1 = sweeps[0]
        label2, bins2 = sweeps[1]

        assert label1 == "2019-06-16 10:00:00"
        assert label2 == "2019-06-16 10:01:00"
        assert len(bins1) == 2
        assert len(bins2) == 2

        # Sweep 1 values
        assert bins1[0].dbm_average == -10.0
        assert bins1[1].dbm_average == -11.0
        # Sweep 2 values
        assert bins2[0].dbm_average == -12.0
        assert bins2[1].dbm_average == -13.0

    def test_three_sweeps_temporal_order(self):
        """Sweeps are returned in the order they appear in the file."""
        parser = SweepParser()
        for t, val in [("08:00:00", -1.0), ("09:00:00", -2.0), ("10:00:00", -3.0)]:
            parser.add_line(
                f"2020-01-01,{t},100000000,101000000,1000000.00,1,{val}"
            )
        sweeps = parser.convert()
        assert len(sweeps) == 3
        assert [s[0] for s in sweeps] == [
            "2020-01-01 08:00:00",
            "2020-01-01 09:00:00",
            "2020-01-01 10:00:00",
        ]

    def test_merge_within_sweep(self):
        """Duplicate frequency keys within the same sweep are averaged."""
        parser = SweepParser()
        # Two lines with same timestamp and overlapping frequency
        parser.add_line(
            "2019-06-16,10:00:00,100000000,102000000,1000000.00,1,-10.0,-20.0,-30.0"
        )
        parser.add_line(
            "2019-06-16,10:00:00,102000000,104000000,1000000.00,1,-40.0,-50.0,-60.0"
        )
        sweeps = parser.convert()
        assert len(sweeps) == 1
        _, bins = sweeps[0]

        # Frequencies: 100M, 101M, 102M (merged), 103M, 104M
        freq_map = {b.frequency_start_parsed: b.dbm_average for b in bins}
        assert freq_map[100000000] == -10.0
        assert freq_map[101000000] == -20.0
        # 102M appears in both lines: (-30 + -40) / 2 = -35
        assert freq_map[102000000] == pytest.approx(-35.0)
        assert freq_map[103000000] == -50.0
        assert freq_map[104000000] == -60.0

    def test_nan_skipped_in_sweep(self):
        """NaN dBm values are silently skipped."""
        parser = SweepParser()
        parser.add_line(
            "2019-06-16,10:00:00,100000000,101000000,1000000.00,1,nan,-5.0"
        )
        sweeps = parser.convert()
        assert len(sweeps) == 1
        _, bins = sweeps[0]
        # Only the non-nan bin should appear
        assert len(bins) == 1
        assert bins[0].frequency_start_parsed == 101000000
        assert bins[0].dbm_average == -5.0


class TestLoadCsvSweeps:
    """Tests for the load_csv_sweeps I/O function."""

    def test_file_not_found(self):
        """Non-existent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_csv_sweeps("/nonexistent/path.csv")

    def test_test_csv_single_sweep(self, test_csv: Path):
        """test.csv has all lines with the same timestamp → 1 sweep."""
        sweeps = load_csv_sweeps(test_csv)
        assert len(sweeps) == 1
        _, bins = sweeps[0]
        # test.csv has 3 lines × 2 dBm cols = up to 4 unique bins
        assert len(bins) == 4

    def test_validation_csv_seven_sweeps(self, validation_csv: Path):
        """test_validation.csv contains 7 sweeps with 921 bins each."""
        sweeps = load_csv_sweeps(validation_csv)
        assert len(sweeps) == 7

        # Each sweep should have 921 unique frequency bins
        for label, bins in sweeps:
            assert len(bins) == 921, (
                f"Sweep {label} has {len(bins)} bins, expected 921"
            )

    def test_validation_sweep_timestamps(self, validation_csv: Path):
        """Sweep timestamps are in chronological order."""
        sweeps = load_csv_sweeps(validation_csv)
        labels = [label for label, _ in sweeps]

        # All on same date
        assert all("2026-02-15" in lbl for lbl in labels)

        # Timestamps should be monotonically increasing
        times = [lbl.split()[-1] for lbl in labels]
        assert times == sorted(times)

    def test_validation_frequency_range(self, validation_csv: Path):
        """Each sweep covers 80 MHz to 1 GHz."""
        sweeps = load_csv_sweeps(validation_csv)
        for _label, bins in sweeps:
            assert bins[0].frequency_start_parsed == 80000000
            assert bins[-1].frequency_start_parsed == 1000000000
