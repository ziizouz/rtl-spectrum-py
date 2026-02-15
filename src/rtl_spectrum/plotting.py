"""Interactive spectrum plotting with Plotly.

This module provides functions to create interactive spectral plots
using Plotly, with support for multi-series overlay, formatted axes,
crosshair hover, NaN gap handling, waterfall/spectrogram heatmaps,
and min/max/avg envelope visualizations.
"""

from pathlib import Path
from typing import List, Optional, Tuple, Union

from rtl_spectrum.formatters import format_frequency, format_power
from rtl_spectrum.models import BinData

try:
    import plotly.graph_objects as go
except ImportError:  # pragma: no cover
    go = None  # type: ignore[assignment]


#: SDR-style colorscale matching common tools (GQRX, SDR#, etc.).
#: Gradient: dark navy → blue → green → yellow → red.
SDR_COLORSCALE: List[List[object]] = [
    [0.0, "#000080"],
    [0.25, "#0000ff"],
    [0.5, "#00ff00"],
    [0.75, "#ffff00"],
    [1.0, "#ff0000"],
]


def _save_figure(
    fig: object,
    output: Union[str, Path],
) -> None:
    """Save a Plotly figure to file.

    Args:
        fig: A Plotly :class:`~plotly.graph_objects.Figure`.
        output: Destination path.  ``.html`` → interactive HTML;
            any other extension → static image via ``kaleido``.
    """
    output = Path(output)
    if output.suffix.lower() == ".html":
        fig.write_html(str(output))  # type: ignore[union-attr]
    else:
        fig.write_image(str(output))  # type: ignore[union-attr]


def plot_spectrum(
    datasets: List[Tuple[str, List[BinData]]],
    title: str = "RF Spectrum",
    show: bool = True,
    output: Optional[Union[str, Path]] = None,
) -> Optional[object]:
    """Create an interactive spectrum plot.

    Args:
        datasets: List of ``(name, data)`` tuples.  Each *data* is a
            list of :class:`~rtl_spectrum.models.BinData`.  Multiple
            entries produce overlaid traces.
        title: Chart title.
        show: If ``True``, opens the plot in the default browser.
        output: Optional file path to save the plot.  ``.html`` files
            are saved as interactive HTML; other extensions (e.g.
            ``.png``) are saved as static images via ``kaleido``.

    Returns:
        The Plotly :class:`~plotly.graph_objects.Figure` object, or
        ``None`` if Plotly is not installed.
    """
    if go is None:  # pragma: no cover
        raise ImportError("plotly is required for plotting. Install with: pip install plotly")

    fig = go.Figure()

    for name, data in datasets:
        freqs = [b.frequency_start_parsed for b in data]
        dbms = [b.dbm_average for b in data]
        hover_texts = [
            f"{format_frequency(f)}<br>{format_power(d)} dBm"
            for f, d in zip(freqs, dbms)
        ]
        fig.add_trace(go.Scatter(
            x=freqs,
            y=dbms,
            mode="lines",
            name=name,
            hovertext=hover_texts,
            hoverinfo="text",
            connectgaps=False,
        ))

    fig.update_layout(
        title=title,
        xaxis_title="Frequency",
        yaxis_title="Power (dBm)",
        hovermode="x unified",
        template="plotly_dark",
        xaxis=dict(
            tickformat=",",
            hoverformat=",",
        ),
    )

    if output:
        _save_figure(fig, output)

    if show:
        fig.show()

    return fig


def plot_waterfall(
    sweeps: List[Tuple[str, List[BinData]]],
    title: str = "RF Waterfall / Spectrogram",
    show: bool = True,
    output: Optional[Union[str, Path]] = None,
) -> Optional[object]:
    """Create a waterfall/spectrogram heatmap plot.

    Renders a Plotly heatmap with X = frequency, Y = sweep timestamp,
    and color = power (dBm) using the fixed :data:`SDR_COLORSCALE`
    (dark navy → blue → green → yellow → red) consistent with
    common SDR tools.

    Args:
        sweeps: List of ``(timestamp_label, bins)`` tuples as
            returned by :func:`~rtl_spectrum.io.load_csv_sweeps`.
        title: Chart title.
        show: If ``True``, opens the plot in the default browser.
        output: Optional file path to save the plot.

    Returns:
        The Plotly :class:`~plotly.graph_objects.Figure` object, or
        ``None`` if Plotly is not installed.

    Raises:
        ValueError: If *sweeps* is empty.
    """
    if go is None:  # pragma: no cover
        raise ImportError("plotly is required for plotting. Install with: pip install plotly")

    if not sweeps:
        raise ValueError("Cannot plot waterfall with empty sweeps")

    # Build a unified frequency axis from all sweeps
    all_freqs: set = set()
    for _label, bins in sweeps:
        for b in bins:
            all_freqs.add(b.frequency_start_parsed)
    freq_axis = sorted(all_freqs)
    freq_index = {f: i for i, f in enumerate(freq_axis)}

    # Build the Z matrix (rows = sweeps, cols = frequencies)
    timestamps: List[str] = []
    z_matrix: List[List[Optional[float]]] = []

    for label, bins in sweeps:
        timestamps.append(label)
        row: List[Optional[float]] = [None] * len(freq_axis)
        for b in bins:
            idx = freq_index[b.frequency_start_parsed]
            row[idx] = b.dbm_average
        z_matrix.append(row)

    fig = go.Figure(data=go.Heatmap(
        x=freq_axis,
        y=timestamps,
        z=z_matrix,
        colorscale=SDR_COLORSCALE,
        colorbar=dict(title="Power (dBm)"),
        hovertemplate=(
            "Frequency: %{x:,} Hz<br>"
            "Time: %{y}<br>"
            "Power: %{z:.2f} dBm"
            "<extra></extra>"
        ),
    ))

    fig.update_layout(
        title=title,
        xaxis_title="Frequency (Hz)",
        yaxis_title="Sweep Time",
        template="plotly_dark",
        xaxis=dict(tickformat=","),
    )

    if output:
        _save_figure(fig, output)

    if show:
        fig.show()

    return fig


def plot_envelope(
    min_series: List[BinData],
    max_series: List[BinData],
    avg_series: List[BinData],
    title: str = "RF Spectrum Envelope",
    show: bool = True,
    output: Optional[Union[str, Path]] = None,
) -> Optional[object]:
    """Create an envelope plot showing min/max band with average line.

    Renders a filled area between the minimum and maximum power at
    each frequency, with the average power drawn as a solid line
    on top.

    Args:
        min_series: Minimum power at each frequency across sweeps.
        max_series: Maximum power at each frequency across sweeps.
        avg_series: Average power at each frequency across sweeps.
        title: Chart title.
        show: If ``True``, opens the plot in the default browser.
        output: Optional file path to save the plot.

    Returns:
        The Plotly :class:`~plotly.graph_objects.Figure` object, or
        ``None`` if Plotly is not installed.
    """
    if go is None:  # pragma: no cover
        raise ImportError("plotly is required for plotting. Install with: pip install plotly")

    freqs_min = [b.frequency_start_parsed for b in min_series]
    dbm_min = [b.dbm_average for b in min_series]
    freqs_max = [b.frequency_start_parsed for b in max_series]
    dbm_max = [b.dbm_average for b in max_series]
    freqs_avg = [b.frequency_start_parsed for b in avg_series]
    dbm_avg = [b.dbm_average for b in avg_series]

    fig = go.Figure()

    # Max trace (upper bound of filled area)
    fig.add_trace(go.Scatter(
        x=freqs_max,
        y=dbm_max,
        mode="lines",
        name="Max",
        line=dict(color="#ff4444", width=1.5),
        hovertext=[
            f"{format_frequency(f)}<br>Max: {format_power(d)} dBm"
            for f, d in zip(freqs_max, dbm_max)
        ],
        hoverinfo="text",
    ))

    # Min trace (lower bound, fills to max)
    fig.add_trace(go.Scatter(
        x=freqs_min,
        y=dbm_min,
        mode="lines",
        name="Min",
        line=dict(color="#4488ff", width=1.5),
        fill="tonexty",
        fillcolor="rgba(100, 100, 255, 0.15)",
        hovertext=[
            f"{format_frequency(f)}<br>Min: {format_power(d)} dBm"
            for f, d in zip(freqs_min, dbm_min)
        ],
        hoverinfo="text",
    ))

    # Average trace (center line)
    fig.add_trace(go.Scatter(
        x=freqs_avg,
        y=dbm_avg,
        mode="lines",
        name="Average",
        line=dict(color="#00ff00", width=2),
        hovertext=[
            f"{format_frequency(f)}<br>Avg: {format_power(d)} dBm"
            for f, d in zip(freqs_avg, dbm_avg)
        ],
        hoverinfo="text",
    ))

    fig.update_layout(
        title=title,
        xaxis_title="Frequency",
        yaxis_title="Power (dBm)",
        hovermode="x unified",
        template="plotly_dark",
        xaxis=dict(tickformat=",", hoverformat=","),
    )

    if output:
        _save_figure(fig, output)

    if show:
        fig.show()

    return fig
