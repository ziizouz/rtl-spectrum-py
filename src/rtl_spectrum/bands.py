"""Frequency band allocation lookup for hover annotations.

This module loads a YAML frequency allocation table (e.g. the Finnish
national frequency allocation) and provides fast lookup of the band
or sub-band that contains a given frequency.  The results are used
to enrich Plotly hover tooltips in interactive (HTML) plots.

The YAML format is a list of entries, each with::

    - primary_service_category: BROADCASTING
      primary_frequency_range:
      - 87500.0      # start in kHz
      - 108000.0     # end in kHz
      subbands:
      - frequency_range:
        - 87500.0
        - 108000.0
        width: 20500.0
        usage: FM Radio
        technical_parameters: ...

All frequency values in the YAML are in **kHz**.  Internally this
module converts them to **Hz** so they match
:attr:`~rtl_spectrum.models.BinData.frequency_start_parsed`.
"""

import bisect
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Union

import yaml

from rtl_spectrum.formatters import format_frequency


@dataclass
class BandInfo:
    """A single frequency band or sub-band allocation.

    Attributes:
        start_hz: Lower edge of the band in Hz (inclusive).
        end_hz: Upper edge of the band in Hz (exclusive).
        width_khz: Bandwidth in kHz as stated in the YAML.
        usage: Human-readable usage description
            (e.g. ``"FM Radio"``).
        primary_service: The parent primary service category
            (e.g. ``"BROADCASTING"``).
    """

    start_hz: int = 0
    end_hz: int = 0
    width_khz: float = 0.0
    usage: str = ""
    primary_service: str = ""


@dataclass
class BandTable:
    """Sorted table of :class:`BandInfo` entries for fast lookup.

    Attributes:
        bands: Sorted list of :class:`BandInfo` (by ``start_hz``).
        starts: Parallel list of ``start_hz`` values for
            :func:`bisect.bisect_right`.
    """

    bands: List[BandInfo] = field(default_factory=list)
    starts: List[int] = field(default_factory=list)


def _khz_to_hz(khz: float) -> int:
    """Convert a frequency in kHz to Hz (integer)."""
    return int(khz * 1000)


#: Maximum number of entries inspected by :func:`validate_bands_yaml`.
_VALIDATE_MAX_ENTRIES = 5


def validate_bands_yaml(data: object) -> None:
    """Validate that parsed YAML data has the expected band structure.

    Inspects up to :data:`_VALIDATE_MAX_ENTRIES` entries to confirm
    the file matches the allocation table format.  Checks:

    1. Top-level value is a ``list``.
    2. Each inspected entry is a ``dict`` with:
       - ``primary_service_category`` — a non-empty string.
       - ``primary_frequency_range`` — a list of exactly 2 numbers.
       - ``subbands`` — a list.

    Args:
        data: The object returned by ``yaml.safe_load()``.

    Raises:
        ValueError: If the data does not conform to the expected
            structure.  The message describes the first problem found.
    """
    if not isinstance(data, list):
        raise ValueError(
            "Invalid band YAML: expected a list of entries, "
            f"got {type(data).__name__}"
        )
    if len(data) == 0:
        raise ValueError("Invalid band YAML: file contains an empty list")

    for i, entry in enumerate(data[:_VALIDATE_MAX_ENTRIES]):
        label = f"entry {i}"
        if not isinstance(entry, dict):
            raise ValueError(
                f"Invalid band YAML: {label} is not a mapping "
                f"(got {type(entry).__name__})"
            )

        # primary_service_category
        psc = entry.get("primary_service_category")
        if not isinstance(psc, str) or not psc.strip():
            raise ValueError(
                f"Invalid band YAML: {label} is missing or has an "
                "empty 'primary_service_category'"
            )

        # primary_frequency_range
        pfr = entry.get("primary_frequency_range")
        if not isinstance(pfr, list) or len(pfr) != 2:
            raise ValueError(
                f"Invalid band YAML: {label} 'primary_frequency_range' "
                "must be a list of exactly 2 numbers"
            )
        for j, val in enumerate(pfr):
            if not isinstance(val, (int, float)):
                raise ValueError(
                    f"Invalid band YAML: {label} "
                    f"'primary_frequency_range[{j}]' is not a number "
                    f"(got {type(val).__name__})"
                )

        # subbands
        sb = entry.get("subbands")
        if not isinstance(sb, list):
            raise ValueError(
                f"Invalid band YAML: {label} 'subbands' must be a list"
            )


def load_bands(path: Union[str, Path]) -> BandTable:
    """Load a frequency allocation YAML file into a :class:`BandTable`.

    Each YAML entry contributes one or more :class:`BandInfo` rows:

    * Every *sub-band* with a valid ``frequency_range`` of two
      values and a ``usage`` field becomes its own row.
    * The parent ``primary_service_category`` is stored on each row
      for fallback display.

    The resulting list is sorted by ``start_hz`` with narrower bands
    placed *after* wider bands that share the same start.  This
    ensures :func:`lookup_band` returns the narrowest (most
    specific) match.

    Args:
        path: Path to the YAML allocation table.

    Returns:
        A :class:`BandTable` ready for :func:`lookup_band`.

    Raises:
        FileNotFoundError: If *path* does not exist.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Band allocation file not found: {path}")

    with open(path, "r", encoding="utf-8") as fh:
        entries = yaml.safe_load(fh)

    validate_bands_yaml(entries)

    all_bands: List[BandInfo] = []

    for entry in entries:
        primary = entry.get("primary_service_category", "")
        pfr = entry.get("primary_frequency_range", [])
        if not pfr or len(pfr) < 2:
            continue

        primary_start_hz = _khz_to_hz(pfr[0])
        primary_end_hz = _khz_to_hz(pfr[1])

        subbands = entry.get("subbands", [])
        has_subband = False

        for sb in subbands:
            fr = sb.get("frequency_range", [])
            if len(fr) < 2:
                continue
            usage = sb.get("usage", "")
            if not usage:
                continue
            width = sb.get("width", 0.0) or 0.0
            has_subband = True
            all_bands.append(BandInfo(
                start_hz=_khz_to_hz(fr[0]),
                end_hz=_khz_to_hz(fr[1]),
                width_khz=float(width),
                usage=usage,
                primary_service=primary,
            ))

        # If no usable subbands, create a fallback from the primary range
        if not has_subband:
            all_bands.append(BandInfo(
                start_hz=primary_start_hz,
                end_hz=primary_end_hz,
                width_khz=float(pfr[1] - pfr[0]),
                usage=primary,
                primary_service=primary,
            ))

    # Sort by start_hz; for ties, wider bands first so narrower
    # (more specific) bands appear later and win in lookup.
    all_bands.sort(key=lambda b: (b.start_hz, -(b.end_hz - b.start_hz)))

    starts = [b.start_hz for b in all_bands]
    return BandTable(bands=all_bands, starts=starts)


def lookup_band(freq_hz: int, table: BandTable) -> Optional[BandInfo]:
    """Find the narrowest band containing *freq_hz*.

    Uses :func:`bisect.bisect_right` on the sorted ``starts`` list
    to find candidate bands whose ``start_hz <= freq_hz``, then
    scans backwards to pick the narrowest enclosing band.

    Args:
        freq_hz: Frequency in Hz.
        table: A :class:`BandTable` returned by :func:`load_bands`.

    Returns:
        The narrowest :class:`BandInfo` whose
        ``[start_hz, end_hz)`` contains *freq_hz*, or ``None``
        if no band matches.
    """
    idx = bisect.bisect_right(table.starts, freq_hz)
    best: Optional[BandInfo] = None
    best_width = float("inf")

    # Scan backwards from idx-1; stop when start_hz is too far below
    for i in range(idx - 1, -1, -1):
        band = table.bands[i]
        if band.start_hz > freq_hz:
            continue
        # Once we pass a band whose end is below freq, and whose
        # start is also much lower, remaining bands are even lower.
        if band.end_hz <= freq_hz:
            # If we already have a match, no need to keep scanning
            if best is not None:
                break
            continue
        # band.start_hz <= freq_hz < band.end_hz  → hit
        width = band.end_hz - band.start_hz
        if width < best_width:
            best = band
            best_width = width

    return best


def format_band_hover(info: Optional[BandInfo]) -> str:
    """Format a :class:`BandInfo` as an HTML snippet for Plotly hover.

    Produces up to three lines:

    1. 📡 *primary_service* (e.g. ``📡 BROADCASTING``)
    2. Frequency range formatted in human-readable units
       (e.g. ``87.5 MHz – 108 MHz``)
    3. Sub-band *usage* (e.g. ``Usage: FM Radio``)

    Args:
        info: Band info, or ``None`` (returns ``""``).

    Returns:
        HTML string safe for Plotly ``hovertext``, or ``""``
        if *info* is ``None``.
    """
    if info is None:
        return ""

    start_str = format_frequency(info.start_hz)
    end_str = format_frequency(info.end_hz)
    parts = [
        f"📡 {info.primary_service}",
        f"{start_str} – {end_str}",
    ]
    if info.usage and info.usage != info.primary_service:
        parts.append(f"Usage: {info.usage}")

    return "<br>".join(parts)


def _annotate_hover(
    freq_hz: int,
    base_text: str,
    table: Optional[BandTable],
) -> str:
    """Append band annotation to an existing hover text string.

    Args:
        freq_hz: Frequency in Hz.
        base_text: Existing hover text (HTML).
        table: Band table, or ``None`` to skip annotation.

    Returns:
        Enriched hover text with a separator and band info appended,
        or the original *base_text* if *table* is ``None`` or no
        band matches.
    """
    if table is None:
        return base_text
    info = lookup_band(freq_hz, table)
    annotation = format_band_hover(info)
    if not annotation:
        return base_text
    return f"{base_text}<br>───<br>{annotation}"
