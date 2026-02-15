"""Tests for time-aware analysis and plotting functions.

Covers peak_hold, envelope, plot_waterfall, plot_envelope,
and the SDR_COLORSCALE constant.
"""

from pathlib import Path

import plotly.graph_objects as go
import pytest

from rtl_spectrum.analysis import envelope, peak_hold
from rtl_spectrum.io import load_csv_sweeps
from rtl_spectrum.models import BinData
from rtl_spectrum.plotting import SDR_COLORSCALE, plot_envelope, plot_waterfall


# ---------------------------------------------------------------------------
#  Helper to build synthetic sweep data
# ---------------------------------------------------------------------------

def _make_sweep(
    timestamp: str,
    freq_dbm_pairs: list,
) -> tuple:
    """Build a (label, bins) sweep tuple from frequency-dBm pairs.

    Args:
        timestamp: Sweep label, e.g. ``"2020-01-01 10:00:00"``.
        freq_dbm_pairs: List of ``(freq_hz, dbm)`` tuples.

    Returns:
        Tuple matching the SweepParser output format.
    """
    bins = []
    for freq, dbm in freq_dbm_pairs:
        bins.append(BinData(
            date=timestamp.split()[0],
            time=timestamp.split()[1],
            frequency_start=str(freq),
            frequency_start_parsed=freq,
            frequency_end="1000000.00",
            bin_size="1000000.00",
            num_samples="1",
            dbm_average=dbm,
            dbm_total=dbm,
            dbm_count=1,
        ))
    bins.sort(key=lambda b: b.frequency_start_parsed)
    return (timestamp, bins)


# Three synthetic sweeps for deterministic testing:
#
#   Freq     Sweep1  Sweep2  Sweep3  | Min    Max    Avg
#   100 MHz  -10     -20     -15     | -20    -10    -15
#   200 MHz  -5      -8      -11     | -11    -5     -8
#   300 MHz  -30     -25     -20     | -30    -20    -25
#
SWEEP1 = _make_sweep("2020-01-01 10:00:00", [
    (100000000, -10.0),
    (200000000, -5.0),
    (300000000, -30.0),
])
SWEEP2 = _make_sweep("2020-01-01 10:01:00", [
    (100000000, -20.0),
    (200000000, -8.0),
    (300000000, -25.0),
])
SWEEP3 = _make_sweep("2020-01-01 10:02:00", [
    (100000000, -15.0),
    (200000000, -11.0),
    (300000000, -20.0),
])

SWEEPS_3 = [SWEEP1, SWEEP2, SWEEP3]


# ---------------------------------------------------------------------------
#  peak_hold tests
# ---------------------------------------------------------------------------

class TestPeakHold:
    """Tests for the peak_hold function."""

    def test_basic_peak_hold(self):
        """Peak hold returns the maximum dBm at each frequency."""
        result = peak_hold(SWEEPS_3)

        assert len(result) == 3
        freq_map = {b.frequency_start_parsed: b.dbm_average for b in result}
        assert freq_map[100000000] == pytest.approx(-10.0)
        assert freq_map[200000000] == pytest.approx(-5.0)
        assert freq_map[300000000] == pytest.approx(-20.0)

    def test_peak_hold_sorted(self):
        """Result is sorted by frequency."""
        result = peak_hold(SWEEPS_3)
        freqs = [b.frequency_start_parsed for b in result]
        assert freqs == sorted(freqs)

    def test_single_sweep(self):
        """Peak hold of a single sweep equals the sweep itself."""
        result = peak_hold([SWEEP1])
        assert len(result) == 3
        freq_map = {b.frequency_start_parsed: b.dbm_average for b in result}
        assert freq_map[100000000] == pytest.approx(-10.0)
        assert freq_map[200000000] == pytest.approx(-5.0)
        assert freq_map[300000000] == pytest.approx(-30.0)

    def test_empty_raises(self):
        """Empty sweeps list raises ValueError."""
        with pytest.raises(ValueError, match="empty"):
            peak_hold([])

    def test_skip_missing_frequencies(self):
        """Frequencies present in only some sweeps are still included."""
        sweep_a = _make_sweep("2020-01-01 10:00:00", [
            (100000000, -10.0),
            (200000000, -5.0),
        ])
        sweep_b = _make_sweep("2020-01-01 10:01:00", [
            (200000000, -8.0),
            (300000000, -3.0),
        ])
        result = peak_hold([sweep_a, sweep_b])
        assert len(result) == 3
        freq_map = {b.frequency_start_parsed: b.dbm_average for b in result}
        assert freq_map[100000000] == pytest.approx(-10.0)
        assert freq_map[200000000] == pytest.approx(-5.0)   # max(-5, -8)
        assert freq_map[300000000] == pytest.approx(-3.0)


# ---------------------------------------------------------------------------
#  envelope tests
# ---------------------------------------------------------------------------

class TestEnvelope:
    """Tests for the envelope function."""

    def test_basic_envelope(self):
        """Envelope returns correct min, max, avg for each frequency."""
        min_s, max_s, avg_s = envelope(SWEEPS_3)

        assert len(min_s) == 3
        assert len(max_s) == 3
        assert len(avg_s) == 3

        min_map = {b.frequency_start_parsed: b.dbm_average for b in min_s}
        max_map = {b.frequency_start_parsed: b.dbm_average for b in max_s}
        avg_map = {b.frequency_start_parsed: b.dbm_average for b in avg_s}

        # 100 MHz: min=-20, max=-10, avg=-15
        assert min_map[100000000] == pytest.approx(-20.0)
        assert max_map[100000000] == pytest.approx(-10.0)
        assert avg_map[100000000] == pytest.approx(-15.0)

        # 200 MHz: min=-11, max=-5, avg=-8
        assert min_map[200000000] == pytest.approx(-11.0)
        assert max_map[200000000] == pytest.approx(-5.0)
        assert avg_map[200000000] == pytest.approx(-8.0)

        # 300 MHz: min=-30, max=-20, avg=-25
        assert min_map[300000000] == pytest.approx(-30.0)
        assert max_map[300000000] == pytest.approx(-20.0)
        assert avg_map[300000000] == pytest.approx(-25.0)

    def test_envelope_sorted(self):
        """All three series are sorted by frequency."""
        min_s, max_s, avg_s = envelope(SWEEPS_3)
        for series in (min_s, max_s, avg_s):
            freqs = [b.frequency_start_parsed for b in series]
            assert freqs == sorted(freqs)

    def test_single_sweep_envelope(self):
        """Envelope of a single sweep: min == max == avg."""
        min_s, max_s, avg_s = envelope([SWEEP1])
        for min_b, max_b, avg_b in zip(min_s, max_s, avg_s):
            assert min_b.dbm_average == pytest.approx(max_b.dbm_average)
            assert min_b.dbm_average == pytest.approx(avg_b.dbm_average)

    def test_empty_raises(self):
        """Empty sweeps list raises ValueError."""
        with pytest.raises(ValueError, match="empty"):
            envelope([])

    def test_skip_missing_frequencies(self):
        """Frequencies in only some sweeps are still included."""
        sweep_a = _make_sweep("2020-01-01 10:00:00", [
            (100000000, -10.0),
        ])
        sweep_b = _make_sweep("2020-01-01 10:01:00", [
            (100000000, -20.0),
            (200000000, -5.0),
        ])
        min_s, max_s, avg_s = envelope([sweep_a, sweep_b])

        min_map = {b.frequency_start_parsed: b.dbm_average for b in min_s}
        max_map = {b.frequency_start_parsed: b.dbm_average for b in max_s}
        avg_map = {b.frequency_start_parsed: b.dbm_average for b in avg_s}

        # 100 MHz present in both
        assert min_map[100000000] == pytest.approx(-20.0)
        assert max_map[100000000] == pytest.approx(-10.0)
        assert avg_map[100000000] == pytest.approx(-15.0)

        # 200 MHz only in sweep_b
        assert min_map[200000000] == pytest.approx(-5.0)
        assert max_map[200000000] == pytest.approx(-5.0)
        assert avg_map[200000000] == pytest.approx(-5.0)


# ---------------------------------------------------------------------------
#  Validation CSV integration tests
# ---------------------------------------------------------------------------

class TestValidationSweepAnalysis:
    """Integration tests using test_validation.csv."""

    def test_peak_hold_validation(self, validation_csv: Path):
        """Peak hold on validation CSV produces 921 bins."""
        sweeps = load_csv_sweeps(validation_csv)
        result = peak_hold(sweeps)
        assert len(result) == 921

        # Peak should be >= any individual sweep value at each freq
        for _label, bins in sweeps:
            sweep_map = {
                b.frequency_start_parsed: b.dbm_average for b in bins
            }
            for b in result:
                if b.frequency_start_parsed in sweep_map:
                    assert b.dbm_average >= sweep_map[b.frequency_start_parsed] - 1e-10

    def test_envelope_validation(self, validation_csv: Path):
        """Envelope on validation CSV: min <= avg <= max at each freq."""
        sweeps = load_csv_sweeps(validation_csv)
        min_s, max_s, avg_s = envelope(sweeps)

        assert len(min_s) == 921
        assert len(max_s) == 921
        assert len(avg_s) == 921

        for mn, mx, av in zip(min_s, max_s, avg_s):
            assert mn.dbm_average <= av.dbm_average + 1e-10
            assert av.dbm_average <= mx.dbm_average + 1e-10


# ---------------------------------------------------------------------------
#  SDR_COLORSCALE tests
# ---------------------------------------------------------------------------

class TestSdrColorscale:
    """Tests for the SDR_COLORSCALE constant."""

    def test_five_stops(self):
        """Colorscale has exactly 5 gradient stops."""
        assert len(SDR_COLORSCALE) == 5

    def test_start_end_range(self):
        """First stop is 0.0, last is 1.0."""
        assert SDR_COLORSCALE[0][0] == 0.0
        assert SDR_COLORSCALE[-1][0] == 1.0

    def test_monotonic(self):
        """Stop positions are monotonically increasing."""
        positions = [s[0] for s in SDR_COLORSCALE]
        assert positions == sorted(positions)

    def test_colors_are_hex(self):
        """All colors are valid hex strings."""
        for _, color in SDR_COLORSCALE:
            assert isinstance(color, str)
            assert color.startswith("#")
            assert len(color) == 7


# ---------------------------------------------------------------------------
#  plot_waterfall tests
# ---------------------------------------------------------------------------

class TestPlotWaterfall:
    """Tests for the plot_waterfall function."""

    def test_creates_figure(self):
        """Returns a Plotly Figure with a Heatmap trace."""
        fig = plot_waterfall(SWEEPS_3, show=False)
        assert isinstance(fig, go.Figure)
        assert len(fig.data) == 1
        assert isinstance(fig.data[0], go.Heatmap)

    def test_heatmap_dimensions(self):
        """Heatmap Z matrix has correct shape (sweeps × frequencies)."""
        fig = plot_waterfall(SWEEPS_3, show=False)
        heatmap = fig.data[0]
        z = heatmap.z
        assert len(z) == 3       # 3 sweeps
        assert len(z[0]) == 3    # 3 frequencies

    def test_heatmap_colorscale(self):
        """Heatmap uses the SDR colorscale."""
        fig = plot_waterfall(SWEEPS_3, show=False)
        heatmap = fig.data[0]
        # Plotly stores colorscale as tuples internally
        for i, (pos, color) in enumerate(heatmap.colorscale):
            assert pos == SDR_COLORSCALE[i][0]
            assert color == SDR_COLORSCALE[i][1]

    def test_empty_raises(self):
        """Empty sweeps raises ValueError."""
        with pytest.raises(ValueError, match="empty"):
            plot_waterfall([], show=False)

    def test_axis_labels(self):
        """Figure has correct axis titles."""
        fig = plot_waterfall(SWEEPS_3, show=False)
        assert fig.layout.xaxis.title.text == "Frequency (Hz)"
        assert fig.layout.yaxis.title.text == "Sweep Time"

    def test_custom_title(self):
        """Custom title is applied."""
        fig = plot_waterfall(SWEEPS_3, title="My Waterfall", show=False)
        assert fig.layout.title.text == "My Waterfall"


# ---------------------------------------------------------------------------
#  plot_envelope tests
# ---------------------------------------------------------------------------

class TestPlotEnvelope:
    """Tests for the plot_envelope function."""

    def test_creates_figure(self):
        """Returns a Plotly Figure with 3 traces (max, min, avg)."""
        min_s, max_s, avg_s = envelope(SWEEPS_3)
        fig = plot_envelope(min_s, max_s, avg_s, show=False)
        assert isinstance(fig, go.Figure)
        assert len(fig.data) == 3

    def test_trace_names(self):
        """Traces are named Max, Min, and Average."""
        min_s, max_s, avg_s = envelope(SWEEPS_3)
        fig = plot_envelope(min_s, max_s, avg_s, show=False)
        names = [t.name for t in fig.data]
        assert "Max" in names
        assert "Min" in names
        assert "Average" in names

    def test_fill_between(self):
        """Min trace has fill='tonexty' for the band."""
        min_s, max_s, avg_s = envelope(SWEEPS_3)
        fig = plot_envelope(min_s, max_s, avg_s, show=False)
        # Min trace (index 1) should fill to max (index 0)
        min_trace = [t for t in fig.data if t.name == "Min"][0]
        assert min_trace.fill == "tonexty"

    def test_avg_line_color(self):
        """Average trace uses green line."""
        min_s, max_s, avg_s = envelope(SWEEPS_3)
        fig = plot_envelope(min_s, max_s, avg_s, show=False)
        avg_trace = [t for t in fig.data if t.name == "Average"][0]
        assert avg_trace.line.color == "#00ff00"

    def test_custom_title(self):
        """Custom title is applied."""
        min_s, max_s, avg_s = envelope(SWEEPS_3)
        fig = plot_envelope(
            min_s, max_s, avg_s, title="My Envelope", show=False
        )
        assert fig.layout.title.text == "My Envelope"

    def test_axis_labels(self):
        """Figure has correct axis titles."""
        min_s, max_s, avg_s = envelope(SWEEPS_3)
        fig = plot_envelope(min_s, max_s, avg_s, show=False)
        assert fig.layout.xaxis.title.text == "Frequency"
        assert fig.layout.yaxis.title.text == "Power (dBm)"
