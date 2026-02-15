"""End-to-end validation tests using test_validation.csv.

These tests ensure the full pipeline works correctly with real-world
data: loading, subtraction, save/reload, and data integrity checks.
"""

import pytest

from rtl_spectrum.analysis import subtract
from rtl_spectrum.io import load_csv, save_csv


class TestValidationEndToEnd:
    """End-to-end tests with test_validation.csv."""

    def test_load_validation_csv_structure(self, validation_csv) -> None:
        """Verify basic structure of loaded validation data."""
        data = load_csv(validation_csv)

        # 921 unique frequency bins after averaging overlapping sweeps
        assert len(data) == 921

        # First bin at 80 MHz (averaged across sweeps)
        assert data[0].frequency_start_parsed == 80000000
        assert data[0].dbm_average == pytest.approx(-17.05, abs=0.01)

        # Last bin at 1 GHz
        assert data[-1].frequency_start_parsed == 1000000000

        # All frequencies should be monotonically increasing
        for i in range(1, len(data)):
            assert data[i].frequency_start_parsed > data[i - 1].frequency_start_parsed

        # All bins should have non-empty metadata
        for b in data:
            assert b.date != ""
            assert b.time != ""
            assert b.frequency_start != ""
            assert b.num_samples != ""

    def test_self_subtract_all_zeros(self, validation_csv) -> None:
        """Subtracting validation CSV from itself yields all zeros."""
        data = load_csv(validation_csv)
        result = subtract(data, data)

        assert len(result) == len(data)
        for b in result:
            assert b.dbm_average == pytest.approx(0.0, abs=1e-12)

    def test_save_reload_integrity(self, validation_csv, tmp_path) -> None:
        """Full round-trip: load → save → reload → compare."""
        original = load_csv(validation_csv)
        saved_path = tmp_path / "validation_saved.csv"

        save_csv(original, saved_path)
        reloaded = load_csv(saved_path)

        assert len(reloaded) == len(original)
        for orig, rl in zip(original, reloaded):
            assert orig.frequency_start == rl.frequency_start
            assert orig.frequency_start_parsed == rl.frequency_start_parsed
            assert orig.dbm_average == pytest.approx(rl.dbm_average, abs=1e-10)

    def test_subtract_then_save_reload(self, validation_csv, tmp_path) -> None:
        """Load, self-subtract, save the zeros, reload and verify."""
        data = load_csv(validation_csv)
        subtracted = subtract(data, data)

        out_path = tmp_path / "subtracted.csv"
        save_csv(subtracted, out_path)
        reloaded = load_csv(out_path)

        assert len(reloaded) == len(subtracted)
        for b in reloaded:
            assert b.dbm_average == pytest.approx(0.0, abs=1e-10)

    def test_validation_csv_frequency_range(self, validation_csv) -> None:
        """Verify the frequency range spans 80 MHz to 1 GHz."""
        data = load_csv(validation_csv)

        min_freq = data[0].frequency_start_parsed
        max_freq = data[-1].frequency_start_parsed

        assert min_freq == 80000000   # 80 MHz
        assert max_freq == 1000000000  # 1 GHz

    def test_validation_csv_spot_checks(self, validation_csv) -> None:
        """Spot-check specific known values from the validation CSV.

        Values are averaged across multiple overlapping sweeps.
        """
        data = load_csv(validation_csv)
        freq_map = {b.frequency_start_parsed: b.dbm_average for b in data}

        # 80 MHz: averaged across 7 samples
        assert freq_map[80000000] == pytest.approx(-17.05, abs=0.01)
        # 87 MHz: averaged across 14 samples
        assert freq_map[87000000] == pytest.approx(-7.4743, abs=0.01)
        # 88 MHz: averaged across 14 samples
        assert freq_map[88000000] == pytest.approx(-6.3657, abs=0.01)
