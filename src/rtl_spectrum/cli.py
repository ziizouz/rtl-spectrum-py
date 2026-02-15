"""Command-line interface for rtl_spectrum.

Provides a ``click``-based CLI with subcommands for loading,
plotting, subtracting, saving, and running rtl_power scans.

Usage::

    rtl-spectrum load scan.csv
    rtl-spectrum load scan.csv --output spectrum.html
    rtl-spectrum subtract --signal scan.csv --baseline noise.csv
    rtl-spectrum save --input scan.csv --output processed.csv
    rtl-spectrum run --freq-start 24000000 --freq-end 1700000000
"""

from pathlib import Path
from typing import Optional

import click

from rtl_spectrum.analysis import subtract
from rtl_spectrum.io import load_csv, save_csv
from rtl_spectrum.plotting import plot_spectrum
from rtl_spectrum.runner import (
    DEFAULT_CROP,
    DEFAULT_FREQ_END,
    DEFAULT_FREQ_START,
    DEFAULT_GAIN,
    DEFAULT_INTEGRATION,
    DEFAULT_STEP,
    run_rtl_power,
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
def load(csv_file: str, output: Optional[str], no_show: bool, title: str) -> None:
    """Load an rtl_power CSV file and display spectrum plot."""
    click.echo(f"Loading {csv_file}...")
    data = load_csv(csv_file)
    click.echo(f"Loaded {len(data)} frequency bins.")

    plot_spectrum(
        datasets=[("Scan", data)],
        title=title,
        show=not no_show,
        output=output,
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
def plot_cmd(
    csv_files: tuple,
    output: Optional[str],
    no_show: bool,
    title: str,
) -> None:
    """Plot one or more CSV files overlaid on the same chart."""
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
