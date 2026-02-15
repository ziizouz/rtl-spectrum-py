"""Tests for formatters — ported from Java FrequencyFormatterTest and PowerFormatterTest."""

import math

import pytest

from rtl_spectrum.formatters import format_frequency, format_power


class TestFrequencyFormatter:
    """Port of Java FrequencyFormatterTest."""

    def test_format_negative(self) -> None:
        """Negative frequency should return empty string."""
        assert format_frequency(-1) == ""

    def test_format_none(self) -> None:
        """None should return empty string."""
        assert format_frequency(None) == ""

    def test_format_hz(self) -> None:
        """Values below 1 KHz should show Hz."""
        assert format_frequency(10) == "10 Hz"

    def test_format_khz(self) -> None:
        """Values in KHz range with decimal."""
        assert format_frequency(10100) == "10.1 KHz"

    def test_format_mhz(self) -> None:
        """Values in MHz range — trailing zeros stripped."""
        assert format_frequency(10_001_000) == "10 MHz"

    def test_format_ghz(self) -> None:
        """Values in GHz range with decimal."""
        assert format_frequency(10_101_000_000) == "10.1 GHz"

    def test_format_zero(self) -> None:
        """Zero Hz."""
        assert format_frequency(0) == "0 Hz"

    def test_format_exact_khz(self) -> None:
        """Exactly 1 KHz boundary."""
        assert format_frequency(1000) == "1 KHz"

    def test_format_exact_mhz(self) -> None:
        """Exactly 1 MHz boundary."""
        assert format_frequency(1_000_000) == "1 MHz"

    def test_format_exact_ghz(self) -> None:
        """Exactly 1 GHz boundary."""
        assert format_frequency(1_000_000_000) == "1 GHz"


class TestPowerFormatter:
    """Port of Java PowerFormatterTest."""

    def test_format_nan(self) -> None:
        """NaN should return empty string."""
        assert format_power(float("nan")) == ""

    def test_format_none(self) -> None:
        """None should return empty string."""
        assert format_power(None) == ""

    def test_format_value(self) -> None:
        """Standard formatting to 2 decimal places."""
        assert format_power(23.4567) == "23.46"

    def test_format_negative(self) -> None:
        """Negative dBm value."""
        assert format_power(-24.14) == "-24.14"

    def test_format_zero(self) -> None:
        """Zero value."""
        assert format_power(0.0) == "0.00"
