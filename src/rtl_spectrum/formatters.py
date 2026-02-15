"""Human-readable formatters for frequency and power values.

This module provides formatting functions that convert raw numeric
values into human-readable strings with appropriate unit suffixes,
matching the Java ``FrequencyFormatter`` and ``PowerFormatter``
behaviour exactly.
"""

import math
from typing import Optional, Union

# Frequency thresholds
_ONE_KHZ: int = 1_000
_ONE_MHZ: int = 1_000_000
_ONE_GHZ: int = 1_000_000_000


def format_frequency(value: Optional[Union[int, float]]) -> str:
    """Format a frequency in Hz to a human-readable string.

    Uses the same logic as the Java ``FrequencyFormatter``:

    * ``None`` or negative → ``""``
    * < 1 KHz → ``"<n> Hz"``
    * < 1 MHz → ``"<n> KHz"``  (with ``#.#`` formatting)
    * < 1 GHz → ``"<n> MHz"``  (with ``#.#`` formatting)
    * ≥ 1 GHz → ``"<n> GHz"``  (with ``#.#`` formatting)

    The ``#.#`` pattern means: up to 1 decimal place, trailing
    zeros and unnecessary decimal points stripped.

    Args:
        value: Frequency in Hz, or ``None``.

    Returns:
        Formatted string, or ``""`` for ``None`` / negative values.
    """
    if value is None:
        return ""

    int_val = int(value)
    float_val = float(value)

    if int_val < 0:
        return ""

    if int_val < _ONE_KHZ:
        return f"{int_val} Hz"

    if int_val < _ONE_MHZ:
        return f"{_format_decimal(float_val / _ONE_KHZ)} KHz"

    if int_val < _ONE_GHZ:
        return f"{_format_decimal(float_val / _ONE_MHZ)} MHz"

    return f"{_format_decimal(float_val / _ONE_GHZ)} GHz"


def format_power(value: Optional[float]) -> str:
    """Format a power value in dBm to a 2-decimal string.

    Matches the Java ``PowerFormatter`` exactly:

    * ``None`` or ``NaN`` → ``""``
    * Otherwise → formatted to 2 decimal places (e.g. ``"23.46"``)

    Args:
        value: Power in dBm, or ``None``.

    Returns:
        Formatted string, or ``""`` for ``None`` / ``NaN``.
    """
    if value is None or math.isnan(value):
        return ""
    return f"{value:.2f}"


def _format_decimal(value: float) -> str:
    """Format a float with up to 1 decimal place, Java ``#.#`` style.

    Trailing zeros after the decimal point are stripped, matching
    Java's ``DecimalFormat("#.#")``.

    Args:
        value: The number to format.

    Returns:
        Formatted string (e.g. ``"10"`` or ``"10.1"``).
    """
    # Format to 1 decimal place, then strip trailing zero + dot
    formatted = f"{value:.1f}"
    if "." in formatted:
        formatted = formatted.rstrip("0").rstrip(".")
    return formatted
