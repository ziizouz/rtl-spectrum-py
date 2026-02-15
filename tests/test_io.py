"""Tests for file I/O — load and save round-trip."""

import pytest

from rtl_spectrum.io import load_csv, save_csv


class TestLoadCsv:
    """Test CSV loading."""

    def test_load_test_csv(self, test_csv) -> None:
        """Load test.csv and verify 4 unique bins after averaging.

        3 rows * 2 dBm cols = 6 raw sub-bins, but overlapping freqs
        at 25M and 26M get averaged → 4 unique bins.
        """
        data = load_csv(test_csv)
        assert len(data) == 4

        # First bin at 24 MHz
        assert data[0].frequency_start == "24000000"
        assert data[0].dbm_average == pytest.approx(-24.14)
        assert data[0].date == "2019-06-16"
        assert data[0].time == "23:10:56"

        # Last bin at 27 MHz (from row 3, second sub-bin)
        freq_map = {b.frequency_start_parsed: b for b in data}
        assert freq_map[27000000].dbm_average == pytest.approx(14.07)

    def test_load_file_not_found(self, tmp_path) -> None:
        """Loading a non-existent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_csv(tmp_path / "nonexistent.csv")


class TestSaveCsv:
    """Test CSV saving."""

    def test_save_and_reload(self, test_csv, tmp_path) -> None:
        """Save data to CSV and reload — values should match."""
        original = load_csv(test_csv)
        out_path = tmp_path / "output.csv"

        save_csv(original, out_path)
        reloaded = load_csv(out_path)

        assert len(reloaded) == len(original)
        for orig, rl in zip(original, reloaded):
            assert orig.frequency_start == rl.frequency_start
            assert orig.dbm_average == pytest.approx(rl.dbm_average)
            assert orig.date == rl.date
            assert orig.time == rl.time


class TestRoundTripValidationCsv:
    """Round-trip test with the large validation CSV."""

    def test_roundtrip_validation_csv(self, validation_csv, tmp_path) -> None:
        """Load test_validation.csv, save, reload, and compare."""
        original = load_csv(validation_csv)
        out_path = tmp_path / "roundtrip.csv"

        save_csv(original, out_path)
        reloaded = load_csv(out_path)

        assert len(reloaded) == len(original)
        for orig, rl in zip(original, reloaded):
            assert orig.frequency_start == rl.frequency_start
            assert orig.dbm_average == pytest.approx(rl.dbm_average, abs=1e-10)
