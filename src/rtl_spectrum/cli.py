"""Command-line interface for rtl_spectrum.

Provides a ``click``-based CLI with subcommands for loading,
plotting, subtracting, saving, and running rtl_power scans.

Supports multiple visualization modes via ``--mode``:
  - ``average`` — traditional averaged spectrum (default)
  - ``waterfall`` — spectrogram heatmap (X=freq, Y=time, color=dBm)
  - ``peak`` — peak-hold (max power per frequency across sweeps)
  - ``envelope`` — min/max/avg band across sweeps

Usage::

    rtl-spectrum load scan.csv
    rtl-spectrum load scan.csv --mode waterfall
    rtl-spectrum load scan.csv --mode peak --output peak.html
    rtl-spectrum load scan.csv --mode envelope
    rtl-spectrum subtract --signal scan.csv --baseline noise.csv
    rtl-spectrum save --input scan.csv --output processed.csv
    rtl-spectrum run --freq-start 24000000 --freq-end 1700000000
"""

from pathlib import Path
from typing import Optional

import click

from rtl_spectrum.analysis import envelope, peak_hold, subtract
from rtl_spectrum.bands import load_bands
from rtl_spectrum.io import load_csv, load_csv_sweeps, save_csv
from rtl_spectrum.plotting import plot_envelope, plot_spectrum, plot_waterfall
from rtl_spectrum.runner import (
    DEFAULT_CROP,
    DEFAULT_FREQ_END,
    DEFAULT_FREQ_START,
    DEFAULT_GAIN,
    DEFAULT_INTEGRATION,
    DEFAULT_STEP,
    run_rtl_power,
)

#: Valid visualization mode choices for the ``--mode`` option.
MODE_CHOICES = click.Choice(
    ["average", "waterfall", "peak", "envelope"],
    case_sensitive=False,
)


def _dispatch_mode(
    mode: str,
    csv_file: str,
    title: str,
    show: bool,
    output: Optional[str],
    bands_file: Optional[str] = None,
) -> None:
    """Load data and dispatch to the correct analysis + plot path.

    Args:
        mode: One of ``average``, ``waterfall``, ``peak``, ``envelope``.
        csv_file: Path to the rtl_power CSV file.
        title: Plot title.
        show: Whether to open the plot in the browser.
        output: Optional file path to save the plot.
        bands_file: Optional path to a frequency allocation YAML file
            for hover annotations.
    """
    bands = None
    if bands_file:
        try:
            bands = load_bands(bands_file)
        except FileNotFoundError as exc:
            raise click.ClickException(str(exc))
        except ValueError as exc:
            raise click.ClickException(str(exc))
        click.echo(f"Loaded {len(bands.bands)} frequency band entries.")

    if mode == "average":
        data = load_csv(csv_file)
        click.echo(f"Loaded {len(data)} frequency bins.")
        plot_spectrum(
            datasets=[("Scan", data)],
            title=title,
            show=show,
            output=output,
            bands=bands,
        )
    elif mode == "waterfall":
        sweeps = load_csv_sweeps(csv_file)
        total_bins = sum(len(bins) for _, bins in sweeps)
        click.echo(
            f"Loaded {len(sweeps)} sweeps, "
            f"{total_bins} total bins."
        )
        plot_waterfall(
            sweeps=sweeps,
            title=title,
            show=show,
            output=output,
            bands=bands,
        )
    elif mode == "peak":
        sweeps = load_csv_sweeps(csv_file)
        click.echo(f"Loaded {len(sweeps)} sweeps.")
        peak_data = peak_hold(sweeps)
        click.echo(f"Peak hold: {len(peak_data)} frequency bins.")
        plot_spectrum(
            datasets=[("Peak Hold", peak_data)],
            title=title,
            show=show,
            output=output,
            bands=bands,
        )
    elif mode == "envelope":
        sweeps = load_csv_sweeps(csv_file)
        click.echo(f"Loaded {len(sweeps)} sweeps.")
        min_s, max_s, avg_s = envelope(sweeps)
        click.echo(f"Envelope: {len(avg_s)} frequency bins.")
        plot_envelope(
            min_series=min_s,
            max_series=max_s,
            avg_series=avg_s,
            title=title,
            show=show,
            output=output,
            bands=bands,
        )


@click.group()
@click.version_option(package_name="rtl-spectrum")
def cli() -> None:
    """rtl-spectrum — spectral analysis tool for rtl_power data."""


@cli.command()
@click.argument("csv_file", type=click.Path(exists=True))
@click.option("--output", "-o", type=click.Path(), default=None,
              help="Save plot to file (.html for interactive, .png for static).")
@click.option("--no-show", is_flag=True, default=False,
              help="Do not open the plot in a browser.")
@click.option("--title", "-t", default="RF Spectrum",
              help="Plot title.")
@click.option("--mode", "-m", type=MODE_CHOICES, default="average",
              help="Visualization mode: average, waterfall, peak, or envelope.")
@click.option("--bands", type=click.Path(), default=None,
              help="Path to a frequency allocation YAML file for hover annotations.")
def load(csv_file: str, output: Optional[str], no_show: bool,
         title: str, mode: str, bands: Optional[str]) -> None:
    """Load an rtl_power CSV file and display spectrum plot."""
    click.echo(f"Loading {csv_file}...")
    _dispatch_mode(
        mode=mode,
        csv_file=csv_file,
        title=title,
        show=not no_show,
        output=output,
        bands_file=bands,
    )


@cli.command()
@click.option("--signal", "-s", required=True,
              type=click.Path(exists=True),
              help="Signal CSV file.")
@click.option("--baseline", "-b", required=True,
              type=click.Path(exists=True),
              help="Baseline/noise-floor CSV file to subtract.")
@click.option("--output", "-o", type=click.Path(), default=None,
              help="Save result to CSV file.")
@click.option("--plot-output", type=click.Path(), default=None,
              help="Save plot to file.")
@click.option("--no-show", is_flag=True, default=False,
              help="Do not open the plot in a browser.")
@click.option("--title", "-t", default="Subtracted Spectrum",
              help="Plot title.")
def subtract_cmd(
    signal: str,
    baseline: str,
    output: Optional[str],
    plot_output: Optional[str],
    no_show: bool,
    title: str,
) -> None:
    """Subtract baseline from signal and display/save result."""
    click.echo(f"Loading signal: {signal}")
    signal_data = load_csv(signal)
    click.echo(f"Loading baseline: {baseline}")
    baseline_data = load_csv(baseline)

    click.echo("Subtracting baseline...")
    result = subtract(signal_data, baseline_data)
    click.echo(f"Result: {len(result)} frequency bins.")

    if output:
        save_csv(result, output)
        click.echo(f"Saved to {output}")

    plot_spectrum(
        datasets=[("Subtracted", result)],
        title=title,
        show=not no_show,
        output=plot_output,
    )


@cli.command()
@click.option("--input", "-i", "input_file", required=True,
              type=click.Path(exists=True),
              help="Input CSV file to re-export.")
@click.option("--output", "-o", required=True,
              type=click.Path(),
              help="Output CSV file path.")
def save(input_file: str, output: str) -> None:
    """Load a CSV and re-export in rtl_power format."""
    click.echo(f"Loading {input_file}...")
    data = load_csv(input_file)
    save_csv(data, output)
    click.echo(f"Saved {len(data)} bins to {output}")


@cli.command(name="plot")
@click.argument("csv_files", nargs=-1, required=True,
                type=click.Path(exists=True))
@click.option("--output", "-o", type=click.Path(), default=None,
              help="Save plot to file.")
@click.option("--no-show", is_flag=True, default=False,
              help="Do not open the plot in a browser.")
@click.option("--title", "-t", default="RF Spectrum",
              help="Plot title.")
@click.option("--mode", "-m", type=MODE_CHOICES, default="average",
              help="Visualization mode: average, waterfall, peak, or envelope.")
@click.option("--bands", type=click.Path(), default=None,
              help="Path to a frequency allocation YAML file for hover annotations.")
def plot_cmd(
    csv_files: tuple,
    output: Optional[str],
    no_show: bool,
    title: str,
    mode: str,
    bands: Optional[str],
) -> None:
    """Plot one or more CSV files overlaid on the same chart.

    For waterfall, peak, and envelope modes, only the first CSV file
    is used.  For average mode, all files are overlaid.
    """
    bands_table = None
    if bands:
        try:
            bands_table = load_bands(bands)
        except FileNotFoundError as exc:
            raise click.ClickException(str(exc))
        except ValueError as exc:
            raise click.ClickException(str(exc))
        click.echo(f"Loaded {len(bands_table.bands)} frequency band entries.")

    if mode != "average":
        # Time-aware modes operate on a single file
        csv_file = csv_files[0]
        if len(csv_files) > 1:
            click.echo(
                f"Warning: --mode {mode} uses only the first file; "
                f"ignoring {len(csv_files) - 1} additional file(s)."
            )
        click.echo(f"Loading {csv_file}...")
        _dispatch_mode(
            mode=mode,
            csv_file=csv_file,
            title=title,
            show=not no_show,
            output=output,
            bands_file=bands,
        )
    else:
        datasets = []
        for csv_file in csv_files:
            click.echo(f"Loading {csv_file}...")
            data = load_csv(csv_file)
            name = Path(csv_file).stem
            datasets.append((name, data))
            click.echo(f"  {len(data)} bins from {name}")

        plot_spectrum(
            datasets=datasets,
            title=title,
            show=not no_show,
            output=output,
            bands=bands_table,
        )


@cli.command()
@click.option("--freq-start", type=int, default=DEFAULT_FREQ_START,
              help=f"Start frequency in Hz (default: {DEFAULT_FREQ_START}).")
@click.option("--freq-end", type=int, default=DEFAULT_FREQ_END,
              help=f"End frequency in Hz (default: {DEFAULT_FREQ_END}).")
@click.option("--step", type=int, default=DEFAULT_STEP,
              help=f"Frequency step in Hz (default: {DEFAULT_STEP}).")
@click.option("--integration", type=int, default=DEFAULT_INTEGRATION,
              help=f"Integration time in seconds (default: {DEFAULT_INTEGRATION}).")
@click.option("--gain", type=int, default=DEFAULT_GAIN,
              help=f"Gain in dB, 0 for auto (default: {DEFAULT_GAIN}).")
@click.option("--crop", type=str, default=DEFAULT_CROP,
              help=f"Crop percentage (default: {DEFAULT_CROP}).")
@click.option("--output", "-o", type=click.Path(), default=None,
              help="Save raw data to CSV file.")
@click.option("--plot-output", type=click.Path(), default=None,
              help="Save plot to file.")
@click.option("--no-show", is_flag=True, default=False,
              help="Do not open the plot in a browser.")
def run(
    freq_start: int,
    freq_end: int,
    step: int,
    integration: int,
    gain: int,
    crop: str,
    output: Optional[str],
    plot_output: Optional[str],
    no_show: bool,
) -> None:
    """Run rtl_power and display the captured spectrum."""
    click.echo("Starting rtl_power scan...")
    data = run_rtl_power(
        freq_start=freq_start,
        freq_end=freq_end,
        step=step,
        integration=integration,
        gain=gain,
        crop=crop,
        progress_callback=lambda msg: click.echo(msg),
    )
    click.echo(f"Captured {len(data)} frequency bins.")

    if output:
        save_csv(data, output)
        click.echo(f"Saved to {output}")

    plot_spectrum(
        datasets=[("Scan", data)],
        title="rtl_power Scan",
        show=not no_show,
        output=plot_output,
    )


if __name__ == "__main__":
    cli()
