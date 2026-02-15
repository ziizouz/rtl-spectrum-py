"""Interactive spectrum plotting with Plotly.

This module provides functions to create interactive spectral plots
using Plotly, with support for multi-series overlay, formatted axes,
crosshair hover, and NaN gap handling.
"""

from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from rtl_spectrum.formatters import format_frequency, format_power
from rtl_spectrum.models import BinData

try:
    import plotly.graph_objects as go
except ImportError:  # pragma: no cover
    go = None  # type: ignore[assignment]


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
        output = Path(output)
        if output.suffix.lower() == ".html":
            fig.write_html(str(output))
        else:
            fig.write_image(str(output))

    if show:
        fig.show()

    return fig
