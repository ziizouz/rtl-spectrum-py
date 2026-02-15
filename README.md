# rtl-spectrum

A modular Python library and CLI for spectral analysis of [rtl_power](https://www.kc1ght.com/sdr/rtl-power) data.

Ported from the Java [rtlSpectrum](https://github.com/dernasherbrezon/rtlSpectrum) project.

## Features

- **Parse** rtl_power CSV output into structured data with automatic multi-bin expansion and frequency averaging
- **Plot** interactive Plotly spectrum charts with multi-series overlay, formatted axes, and HTML/PNG export
- **Subtract** a baseline/noise-floor scan from a signal to isolate real transmissions
- **Run** rtl_power directly from Python with configurable scan parameters
- **Save** processed data back to rtl_power-compatible CSV format
- **CLI** for all operations via `rtl-spectrum` command

## Installation

```bash
# From the project directory
pip install -e .

# With development/test dependencies
pip install -e ".[dev]"
```

### Requirements

- Python ≥ 3.6
- [rtl_power](http://kmkeen.com/rtl-power/) (only required for live scans via the `run` command)

## Quick Start

### CLI

```bash
# Load a CSV and display an interactive spectrum plot
rtl-spectrum load scan.csv

# Save plot to file instead of opening a browser
rtl-spectrum load scan.csv --output spectrum.html --no-show

# Subtract baseline from signal
rtl-spectrum subtract --signal scan.csv --baseline noise.csv

# Save subtracted result to CSV
rtl-spectrum subtract -s scan.csv -b noise.csv --output result.csv

# Plot multiple CSV files overlaid
rtl-spectrum plot scan1.csv scan2.csv --title "Comparison"

# Re-export a CSV (normalises to 7-column format)
rtl-spectrum save --input raw.csv --output clean.csv

# Run a live rtl_power scan (requires RTL-SDR hardware)
rtl-spectrum run --freq-start 88000000 --freq-end 108000000 --step 100000
```

### Python API

```python
from rtl_spectrum.io import load_csv, save_csv
from rtl_spectrum.analysis import subtract
from rtl_spectrum.plotting import plot_spectrum

# Load data
signal = load_csv("scan.csv")
baseline = load_csv("noise.csv")

# Subtract baseline
result = subtract(signal, baseline)

# Plot
plot_spectrum(
    datasets=[("Signal", signal), ("Subtracted", result)],
    title="My Scan",
    output="comparison.html",
)

# Save
save_csv(result, "result.csv")
```

## Project Structure

```
rtl-spectrum-py/
├── pyproject.toml
├── README.md
├── src/
│   └── rtl_spectrum/
│       ├── __init__.py        # Package version
│       ├── models.py          # BinData dataclass
│       ├── parser.py          # CSV parser with multi-bin expansion
│       ├── io.py              # load_csv / save_csv
│       ├── runner.py          # rtl_power subprocess wrapper
│       ├── analysis.py        # Baseline subtraction
│       ├── formatters.py      # Human-readable frequency/power formatting
│       ├── plotting.py        # Interactive Plotly charts
│       ├── progress.py        # Progress reporting
│       └── cli.py             # Click CLI entry point
└── tests/
    ├── conftest.py            # Shared fixtures
    ├── resources/             # Test CSV files
    ├── test_parser.py         # Parser unit tests
    ├── test_formatters.py     # Formatter unit tests
    ├── test_analysis.py       # Subtraction tests
    ├── test_io.py             # I/O round-trip tests
    └── test_validation.py     # End-to-end validation
```

## Modules

### `models.BinData`

Dataclass representing a single frequency bin — the fundamental data unit. Stores original CSV string fields for round-trip fidelity alongside computed numeric values (`frequency_start_parsed`, `dbm_average`).

### `parser.BinDataParser`

Parses rtl_power CSV rows. Each row may contain multiple dBm sub-bins (columns 6+), which are expanded into individual `BinData` entries at `freq_start + i × step`. Overlapping frequency keys across rows are averaged automatically. NaN values are skipped.

### `io`

- `load_csv(path)` — Read an rtl_power CSV file and return a sorted, averaged list of `BinData`.
- `save_csv(data, path)` — Write `BinData` list to a 7-column CSV compatible with rtl_power format.

### `analysis`

- `subtract(signal, baseline)` — Per-frequency-bin subtraction (signal − baseline) in dBm. Matches by exact `frequency_start` string.
- `subtract_multi(signals, baseline)` — Apply subtraction to multiple signal series.

### `runner`

- `run_rtl_power(...)` — Execute `rtl_power` as a subprocess with configurable parameters and return parsed `BinData`.

| Parameter     | Default      | Description                    |
|---------------|--------------|--------------------------------|
| `freq_start`  | 24 MHz       | Start frequency in Hz          |
| `freq_end`    | 1.7 GHz      | End frequency in Hz            |
| `step`        | 1 MHz        | Frequency step in Hz           |
| `integration` | 120 s        | Integration time in seconds    |
| `gain`        | 0 (auto)     | Gain in dB                     |
| `crop`        | 20%          | Edge crop percentage           |

### `formatters`

- `format_frequency(hz)` — Convert Hz to human-readable string (e.g. `"98.1 MHz"`).
- `format_power(dbm)` — Format dBm value to 2 decimal places (e.g. `"-23.45 dBm"`).

### `plotting`

- `plot_spectrum(datasets, ...)` — Create interactive Plotly charts with dark theme, crosshair hover, and optional HTML/PNG export.

## CLI Reference

```
rtl-spectrum [OPTIONS] COMMAND [ARGS]...

Commands:
  load      Load an rtl_power CSV file and display spectrum plot
  plot      Plot one or more CSV files overlaid on the same chart
  run       Run rtl_power and display the captured spectrum
  save      Load a CSV and re-export in rtl_power format
  subtract  Subtract baseline from signal and display/save result
```

Run `rtl-spectrum COMMAND --help` for detailed options on each subcommand.

## Testing

```bash
# Run all tests
python -m pytest tests/ -v

# With coverage
python -m pytest tests/ --cov=rtl_spectrum --cov-report=term-missing
```

## CSV Format

The library reads and writes the standard rtl_power CSV format:

```
date, time, freq_start, freq_end, step, num_samples, dBm1[, dBm2, ...]
```

- **Columns 0–5**: Metadata (date, time, frequency range, step size, sample count)
- **Columns 6+**: Power measurements in dBm — each column represents a sub-bin at `freq_start + i × step`

## License

Apache License 2.0 — see the original [rtlSpectrum](https://github.com/dernasherbrezon/rtlSpectrum) project.
