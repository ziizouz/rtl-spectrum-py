"""Subprocess wrapper for running ``rtl_power``.

This module provides :func:`run_rtl_power`, which executes the
``rtl_power`` command-line tool as a subprocess, streaming its stdout
output through :class:`~rtl_spectrum.parser.BinDataParser` and
returning parsed spectral data.
"""

import subprocess
from typing import Callable, List, Optional

from rtl_spectrum.models import BinData
from rtl_spectrum.parser import BinDataParser

# Default rtl_power parameters (matching the Java constants)
DEFAULT_FREQ_START: int = 24_000_000
"""Default start frequency in Hz (24 MHz)."""

DEFAULT_FREQ_END: int = 1_700_000_000
"""Default end frequency in Hz (1.7 GHz)."""

DEFAULT_STEP: int = 1_000_000
"""Default frequency step in Hz (1 MHz)."""

DEFAULT_INTEGRATION: int = 120
"""Default integration time in seconds (2 minutes)."""

DEFAULT_GAIN: int = 0
"""Default gain in dB (0 = automatic)."""

DEFAULT_CROP: str = "20%"
"""Default crop percentage."""

# Known error strings from rtl_power stderr
_KNOWN_ERRORS = [
    "No supported devices found.",
    "usb_claim_interface",
    "stdbuf:",
]


def run_rtl_power(
    freq_start: int = DEFAULT_FREQ_START,
    freq_end: int = DEFAULT_FREQ_END,
    step: int = DEFAULT_STEP,
    integration: int = DEFAULT_INTEGRATION,
    gain: int = DEFAULT_GAIN,
    crop: str = DEFAULT_CROP,
    progress_callback: Optional[Callable[[str], None]] = None,
) -> List[BinData]:
    """Execute ``rtl_power`` and return parsed spectral data.

    Builds and runs the command::

        rtl_power -f <start>:<end>:<step> -i <integration> -g <gain> -c <crop> -1 -

    Stdout is streamed line-by-line into a :class:`BinDataParser`.
    Stderr is checked for known error patterns.

    Args:
        freq_start: Start frequency in Hz.
        freq_end: End frequency in Hz.
        step: Frequency step in Hz.
        integration: Integration time in seconds.
        gain: Tuner gain in dB (0 for automatic).
        crop: Crop percentage string (e.g. ``"20%"``).
        progress_callback: Optional callable invoked with status
            messages during execution.

    Returns:
        Sorted list of :class:`~rtl_spectrum.models.BinData`.

    Raises:
        RuntimeError: If ``rtl_power`` reports a known error on stderr.
        FileNotFoundError: If ``rtl_power`` is not found on ``$PATH``.
        subprocess.SubprocessError: On other subprocess failures.
    """
    cmd = [
        "rtl_power",
        "-f", f"{freq_start}:{freq_end}:{step}",
        "-i", str(integration),
        "-g", str(gain),
        "-c", crop,
        "-1",
        "-",
    ]

    if progress_callback:
        progress_callback(f"Running: {' '.join(cmd)}")

    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="iso-8859-1",
        )
    except FileNotFoundError:
        raise FileNotFoundError(
            "rtl_power not found. Ensure it is installed and on your $PATH."
        )

    parser = BinDataParser()

    # Read stdout line-by-line
    assert process.stdout is not None
    for line in process.stdout:
        line = line.rstrip("\n\r")
        if line:
            parser.add_line(line)

    # Check stderr for known errors
    assert process.stderr is not None
    stderr_output = process.stderr.read()
    for err_line in stderr_output.splitlines():
        for known in _KNOWN_ERRORS:
            if err_line.strip().lower().startswith(known.lower()) or \
               known.lower() in err_line.lower():
                process.wait()
                raise RuntimeError(f"rtl_power error: {err_line.strip()}")

    process.wait()

    if progress_callback:
        progress_callback("rtl_power completed")

    return parser.convert()
