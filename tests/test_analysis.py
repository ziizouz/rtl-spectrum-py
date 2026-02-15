"""Tests for analysis module — subtraction logic.

Ported from the subtraction assertions in Java UITest:
  load test.csv → subtract subtract.csv → verify (-2.0, -2.0, 2.0).
"""

import pytest

from rtl_spectrum.analysis import subtract, subtract_multi
from rtl_spectrum.io import load_csv


class TestSubtract:
    """Test baseline subtraction matching Java UITest assertions."""

    def test_subtract_test_csv(self, test_csv, subtract_csv) -> None:
        """Subtract subtract.csv from test.csv.

        test.csv rows produce 4 unique bins (24M, 25M, 26M, 27M)
        because adjacent rows overlap at 25M and 26M, getting averaged.

        Expected results:
        - bin 24M: -24.14 - (-22.14) = -2.0
        - bin 25M: avg(-24.14,-24.15) - avg(-22.14,-22.15) = -24.145 - (-22.145) = -2.0
        - bin 26M: avg(-24.15,14.07) - avg(-22.15,12.07) = -5.04 - (-5.04) = 0.0
        - bin 27M: 14.07 - 12.07 = 2.0
        """
        signal = load_csv(test_csv)
        baseline = load_csv(subtract_csv)

        result = subtract(signal, baseline)

        assert len(result) == 4  # 4 unique freq bins after averaging
        freq_to_dbm = {b.frequency_start_parsed: b.dbm_average for b in result}
        assert freq_to_dbm[24000000] == pytest.approx(-2.0)
        assert freq_to_dbm[25000000] == pytest.approx(-2.0)
        assert freq_to_dbm[26000000] == pytest.approx(0.0, abs=1e-10)
        assert freq_to_dbm[27000000] == pytest.approx(2.0)

    def test_subtract_no_match(self) -> None:
        """Subtracting with no matching frequencies returns empty list."""
        from rtl_spectrum.models import BinData

        signal = [BinData(frequency_start="100", frequency_start_parsed=100,
                          dbm_average=-10.0)]
        baseline = [BinData(frequency_start="200", frequency_start_parsed=200,
                            dbm_average=-5.0)]

        result = subtract(signal, baseline)
        assert len(result) == 0

    def test_subtract_self_is_zero(self, test_csv) -> None:
        """Subtracting a file from itself should yield all zeros."""
        data = load_csv(test_csv)
        result = subtract(data, data)

        for b in result:
            assert b.dbm_average == pytest.approx(0.0)

    def test_subtract_multi(self, test_csv, subtract_csv) -> None:
        """Test multi-series subtraction."""
        signal = load_csv(test_csv)
        baseline = load_csv(subtract_csv)

        result = subtract_multi([signal, signal], baseline)

        assert len(result) == 2
        for series in result:
            assert len(series) == 4
            freq_to_dbm = {b.frequency_start_parsed: b.dbm_average for b in series}
            assert freq_to_dbm[24000000] == pytest.approx(-2.0)
