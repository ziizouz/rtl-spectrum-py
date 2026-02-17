# resources/

This directory holds **frequency allocation YAML files** used by the
`--bands` CLI option to add hover annotations on interactive plots.

## Included Files

| File | Description |
|------|-------------|
| `default.yaml` | Small sample with well-known bands (FM Radio, Amateur, ISM, GSM-900, Wi-Fi). Use it as a **format reference** when creating your own allocation file. |

## Creating Your Own Allocation File

1. Copy `default.yaml` to a new file (e.g. `my_country.yaml`).
2. Edit the entries following the same YAML structure — see the inline
   comments in `default.yaml` for field descriptions.
3. All frequencies must be in **kHz** (kilohertz).
4. Pass the full path to your file via the CLI:

```bash
rtl-spectrum load scan.csv --bands /path/to/my_country.yaml
```

## Real-World Example

The **Finnish national frequency allocation table** is a comprehensive
allocation file with ~270 entries and ~1400 sub-bands covering 8.3 kHz
to 275 GHz.  It is available separately and can be used directly:

```bash
rtl-spectrum load scan.csv --bands /path/to/Finnish_frequency_allocation_table.yaml
```

## YAML Format Reference

```yaml
- primary_service_category: BROADCASTING    # Service category name
  primary_frequency_range:
  - 87500.0                                 # Start frequency in kHz
  - 108000.0                                # End frequency in kHz
  subbands:
  - frequency_range:
    - 87500.0                               # Sub-band start in kHz
    - 108000.0                              # Sub-band end in kHz
    width: 20500.0                          # Bandwidth in kHz
    usage: FM Radio                         # Human-readable usage
    technical_parameters:                   # Optional (can be empty)
      mode_of_traffic: ''
```

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `primary_service_category` | string | Top-level service name |
| `primary_frequency_range` | list of 2 floats | Band edges in kHz |
| `subbands` | list | One or more sub-band allocations |

Each sub-band requires:

| Field | Type | Description |
|-------|------|-------------|
| `frequency_range` | list of 2 floats | Sub-band edges in kHz |
| `usage` | string | Human-readable description |
| `width` | float | Bandwidth in kHz (optional) |
