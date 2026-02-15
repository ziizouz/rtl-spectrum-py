"""Tests for BinDataParser — ported from Java BinDataParserTest."""

import pytest

from rtl_spectrum.parser import BinDataParser


class TestBinDataParserMergeIntervals:
    """Port of Java testMergeIntervals.

    Two lines with nan in alternating dBm columns should produce
    2 bins, each with the correct non-nan value.
    """

    def test_merge_intervals(self) -> None:
        parser = BinDataParser()
        parser.add_line("2021-11-14, 20:27:18, 433006, 435994, 58.59, 342414, -27.70, nan")
        parser.add_line("2021-11-14, 20:27:18, 433006, 435994, 58.59, 342414, nan, -26.70")

        result = parser.convert()

        assert len(result) == 2
        assert result[0].frequency_start == "433006"
        assert result[0].dbm_average == pytest.approx(-27.70)
        assert result[1].frequency_start == "433064"
        assert result[1].dbm_average == pytest.approx(-26.70)


class TestBinDataParserAverage:
    """Port of Java testAverage.

    Two lines with the same frequency range but different dBm values
    should produce averaged values: (-30 + -60) / 2 = -45.0
    """

    def test_average(self) -> None:
        parser = BinDataParser()
        parser.add_line("2021-11-14, 20:27:18, 433006, 435994, 58.59, 342414, -30.0, -60.0")
        parser.add_line("2021-11-14, 20:28:18, 433006, 435994, 58.59, 342414, -60.0, -30.0")

        result = parser.convert()

        assert len(result) == 2
        assert result[0].frequency_start == "433006"
        assert result[0].dbm_average == pytest.approx(-45.0)
        assert result[1].frequency_start == "433064"
        assert result[1].dbm_average == pytest.approx(-45.0)


class TestBinDataParserEdgeCases:
    """Additional edge case tests for parser robustness."""

    def test_empty_line_ignored(self) -> None:
        parser = BinDataParser()
        parser.add_line("")
        result = parser.convert()
        assert len(result) == 0

    def test_short_line_ignored(self) -> None:
        parser = BinDataParser()
        parser.add_line("2021-11-14, 20:27:18, 433006")
        result = parser.convert()
        assert len(result) == 0

    def test_all_nan_ignored(self) -> None:
        parser = BinDataParser()
        parser.add_line("2021-11-14, 20:27:18, 433006, 435994, 58.59, 342414, nan, nan")
        result = parser.convert()
        assert len(result) == 0

    def test_single_value(self) -> None:
        parser = BinDataParser()
        parser.add_line("2019-06-16,23:10:56,24000000,25000000,1000000.00,1,-24.14")
        result = parser.convert()
        assert len(result) == 1
        assert result[0].frequency_start == "24000000"
        assert result[0].dbm_average == pytest.approx(-24.14)


class TestBinDataParserValidationCsv:
    """Test parsing the full test_validation.csv file."""

    def test_load_validation_csv(self, validation_csv) -> None:
        parser = BinDataParser()
        with open(validation_csv, "r") as fh:
            line_count = 0
            for line in fh:
                line = line.rstrip("\n\r")
                if line:
                    parser.add_line(line)
                    line_count += 1

        result = parser.convert()

        # The file produces 921 unique frequency bins after averaging
        assert len(result) == 921

        # First bin should be at 80 MHz (averaged across multiple sweeps)
        assert result[0].frequency_start_parsed == 80000000
        assert result[0].dbm_average == pytest.approx(-17.05, abs=0.01)

        # Last bin should be at 1 GHz
        assert result[-1].frequency_start_parsed == 1000000000

        # All bins should be sorted by frequency
        for i in range(1, len(result)):
            assert result[i].frequency_start_parsed > result[i - 1].frequency_start_parsed
