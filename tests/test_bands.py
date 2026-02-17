"""Tests for the frequency band annotation module."""

import os
import textwrap

import pytest

from rtl_spectrum.bands import (
    BandInfo,
    BandTable,
    _annotate_hover,
    _khz_to_hz,
    format_band_hover,
    load_bands,
    lookup_band,
    validate_bands_yaml,
)
from rtl_spectrum.models import BinData

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_YAML = textwrap.dedent("""\
    - primary_service_category: BROADCASTING
      primary_frequency_range:
      - 87500.0
      - 108000.0
      subbands:
      - frequency_range:
        - 87500.0
        - 108000.0
        width: 20500.0
        usage: FM Radio
        technical_parameters:
          mode_of_traffic: ''
    - primary_service_category: AERONAUTICAL RADIONAVIGATION
      primary_frequency_range:
      - 108000.0
      - 117975.0
      subbands:
      - frequency_range:
        - 108000.0
        - 111975.0
        width: 3975.0
        usage: ILS localizer
        technical_parameters:
          mode_of_traffic: ''
      - frequency_range:
        - 111975.0
        - 117975.0
        width: 6000.0
        usage: VOR
        technical_parameters:
          mode_of_traffic: ''
    - primary_service_category: AMATEUR
      primary_frequency_range:
      - 144000.0
      - 146000.0
      subbands:
      - frequency_range:
        - 144000.0
        - 146000.0
        width: 2000.0
        usage: Amateur
        technical_parameters:
          mode_of_traffic: ''
""")


@pytest.fixture
def sample_yaml_path(tmp_path):
    """Write sample YAML to a temp file and return the path."""
    p = tmp_path / "bands.yaml"
    p.write_text(SAMPLE_YAML, encoding="utf-8")
    return p


@pytest.fixture
def sample_table(sample_yaml_path):
    """Load the sample YAML into a BandTable."""
    return load_bands(sample_yaml_path)


# Path to the real Finnish allocation table (may not exist in CI)
FINNISH_YAML = os.path.join(
    os.path.dirname(__file__), os.pardir,
    "resources", "Finnish_frequency_allocation_table.yaml",
)
has_finnish = os.path.exists(FINNISH_YAML)

# Path to the bundled default.yaml sample
DEFAULT_YAML = os.path.join(
    os.path.dirname(__file__), os.pardir,
    "resources", "default.yaml",
)
has_default = os.path.exists(DEFAULT_YAML)


# ---------------------------------------------------------------------------
# TestKhzToHz
# ---------------------------------------------------------------------------

class TestKhzToHz:
    """Unit tests for _khz_to_hz conversion."""

    def test_integer(self):
        assert _khz_to_hz(100.0) == 100_000

    def test_fractional(self):
        assert _khz_to_hz(87.5) == 87_500

    def test_zero(self):
        assert _khz_to_hz(0.0) == 0

    def test_large(self):
        assert _khz_to_hz(275_000_000.0) == 275_000_000_000


# ---------------------------------------------------------------------------
# TestLoadBands
# ---------------------------------------------------------------------------

class TestLoadBands:
    """Tests for load_bands."""

    def test_loads_correct_count(self, sample_table):
        # 1 (FM Radio) + 2 (ILS, VOR) + 1 (Amateur) = 4
        assert len(sample_table.bands) == 4

    def test_sorted_by_start(self, sample_table):
        starts = [b.start_hz for b in sample_table.bands]
        assert starts == sorted(starts)

    def test_khz_to_hz_conversion(self, sample_table):
        fm = [b for b in sample_table.bands if b.usage == "FM Radio"][0]
        assert fm.start_hz == 87_500_000
        assert fm.end_hz == 108_000_000

    def test_width_preserved(self, sample_table):
        fm = [b for b in sample_table.bands if b.usage == "FM Radio"][0]
        assert fm.width_khz == 20500.0

    def test_primary_service(self, sample_table):
        vor = [b for b in sample_table.bands if b.usage == "VOR"][0]
        assert vor.primary_service == "AERONAUTICAL RADIONAVIGATION"

    def test_starts_parallel(self, sample_table):
        assert sample_table.starts == [
            b.start_hz for b in sample_table.bands
        ]

    def test_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="not found"):
            load_bands(tmp_path / "nope.yaml")

    def test_entry_without_usable_subbands(self, tmp_path):
        """Entry whose subbands lack usage → falls back to primary."""
        yaml_text = textwrap.dedent("""\
            - primary_service_category: TEST SERVICE
              primary_frequency_range:
              - 100.0
              - 200.0
              subbands:
              - frequency_range:
                - 100.0
                - 200.0
                width: 100.0
                usage: ''
                technical_parameters:
                  mode_of_traffic: ''
        """)
        p = tmp_path / "sparse.yaml"
        p.write_text(yaml_text, encoding="utf-8")
        table = load_bands(p)
        assert len(table.bands) == 1
        assert table.bands[0].usage == "TEST SERVICE"
        assert table.bands[0].primary_service == "TEST SERVICE"

    @pytest.mark.skipif(not has_finnish, reason="Finnish YAML not present")
    def test_load_finnish_table(self):
        table = load_bands(FINNISH_YAML)
        assert len(table.bands) > 100
        # All bands must have positive frequency range
        for b in table.bands:
            assert b.start_hz < b.end_hz


# ---------------------------------------------------------------------------
# TestLookupBand
# ---------------------------------------------------------------------------

class TestLookupBand:
    """Tests for lookup_band."""

    def test_exact_start(self, sample_table):
        info = lookup_band(87_500_000, sample_table)
        assert info is not None
        assert info.usage == "FM Radio"

    def test_mid_range(self, sample_table):
        info = lookup_band(100_000_000, sample_table)
        assert info is not None
        assert info.usage == "FM Radio"

    def test_end_exclusive(self, sample_table):
        """end_hz is exclusive: 108 MHz is NOT in FM, it's in ILS."""
        info = lookup_band(108_000_000, sample_table)
        assert info is not None
        assert info.usage == "ILS localizer"

    def test_subband_narrower_wins(self, sample_table):
        """Inside the aeronautical range, the narrower subband wins."""
        info = lookup_band(110_000_000, sample_table)
        assert info is not None
        assert info.usage == "ILS localizer"

    def test_second_subband(self, sample_table):
        info = lookup_band(115_000_000, sample_table)
        assert info is not None
        assert info.usage == "VOR"

    def test_no_match_below(self, sample_table):
        info = lookup_band(50_000_000, sample_table)
        assert info is None

    def test_no_match_above(self, sample_table):
        info = lookup_band(200_000_000, sample_table)
        assert info is None

    def test_no_match_gap(self, sample_table):
        """Gap between aeronautical (117.975 MHz) and amateur (144 MHz)."""
        info = lookup_band(130_000_000, sample_table)
        assert info is None

    def test_empty_table(self):
        table = BandTable(bands=[], starts=[])
        assert lookup_band(100_000_000, table) is None

    @pytest.mark.skipif(not has_finnish, reason="Finnish YAML not present")
    def test_finnish_fm_band(self):
        table = load_bands(FINNISH_YAML)
        info = lookup_band(100_000_000, table)
        assert info is not None
        assert "BROADCASTING" in info.primary_service.upper()


# ---------------------------------------------------------------------------
# TestFormatBandHover
# ---------------------------------------------------------------------------

class TestFormatBandHover:
    """Tests for format_band_hover."""

    def test_none_returns_empty(self):
        assert format_band_hover(None) == ""

    def test_contains_primary_service(self):
        info = BandInfo(
            start_hz=87_500_000,
            end_hz=108_000_000,
            width_khz=20500.0,
            usage="FM Radio",
            primary_service="BROADCASTING",
        )
        result = format_band_hover(info)
        assert "BROADCASTING" in result

    def test_contains_frequency_range(self):
        info = BandInfo(
            start_hz=87_500_000,
            end_hz=108_000_000,
            width_khz=20500.0,
            usage="FM Radio",
            primary_service="BROADCASTING",
        )
        result = format_band_hover(info)
        assert "87.5 MHz" in result
        assert "108 MHz" in result

    def test_contains_usage(self):
        info = BandInfo(
            start_hz=87_500_000,
            end_hz=108_000_000,
            width_khz=20500.0,
            usage="FM Radio",
            primary_service="BROADCASTING",
        )
        result = format_band_hover(info)
        assert "Usage: FM Radio" in result

    def test_usage_same_as_primary_not_duplicated(self):
        """When usage == primary_service, don't show Usage: line."""
        info = BandInfo(
            start_hz=144_000_000,
            end_hz=146_000_000,
            width_khz=2000.0,
            usage="AMATEUR",
            primary_service="AMATEUR",
        )
        result = format_band_hover(info)
        assert "Usage:" not in result

    def test_html_line_breaks(self):
        info = BandInfo(
            start_hz=87_500_000,
            end_hz=108_000_000,
            width_khz=20500.0,
            usage="FM Radio",
            primary_service="BROADCASTING",
        )
        result = format_band_hover(info)
        assert "<br>" in result

    def test_emoji_present(self):
        info = BandInfo(
            start_hz=87_500_000,
            end_hz=108_000_000,
            width_khz=20500.0,
            usage="FM Radio",
            primary_service="BROADCASTING",
        )
        result = format_band_hover(info)
        assert "📡" in result


# ---------------------------------------------------------------------------
# TestAnnotateHover
# ---------------------------------------------------------------------------

class TestAnnotateHover:
    """Tests for _annotate_hover helper."""

    def test_no_table_returns_base(self):
        result = _annotate_hover(100_000_000, "base text", None)
        assert result == "base text"

    def test_no_match_returns_base(self):
        table = BandTable(bands=[], starts=[])
        result = _annotate_hover(100_000_000, "base text", table)
        assert result == "base text"

    def test_match_appends_annotation(self, sample_table):
        result = _annotate_hover(100_000_000, "100 MHz", sample_table)
        assert result.startswith("100 MHz")
        assert "───" in result  # separator
        assert "FM Radio" in result

    def test_separator_present(self, sample_table):
        result = _annotate_hover(100_000_000, "base", sample_table)
        assert "<br>───<br>" in result


# ---------------------------------------------------------------------------
# TestPlotIntegration
# ---------------------------------------------------------------------------

class TestPlotIntegration:
    """Integration tests verifying band annotations appear in plots."""

    @pytest.fixture
    def bins_fm(self):
        """Three BinData points in FM band (87.5 - 108 MHz)."""
        return [
            BinData(frequency_start_parsed=90_000_000, dbm_average=-50.0),
            BinData(frequency_start_parsed=95_000_000, dbm_average=-45.0),
            BinData(frequency_start_parsed=100_000_000, dbm_average=-48.0),
        ]

    def test_spectrum_hover_contains_band(self, bins_fm, sample_table):
        from rtl_spectrum.plotting import plot_spectrum
        fig = plot_spectrum(
            datasets=[("Test", bins_fm)],
            show=False,
            bands=sample_table,
        )
        hover = fig.data[0].hovertext
        assert any("FM Radio" in h for h in hover)

    def test_spectrum_no_bands_no_annotation(self, bins_fm):
        from rtl_spectrum.plotting import plot_spectrum
        fig = plot_spectrum(
            datasets=[("Test", bins_fm)],
            show=False,
            bands=None,
        )
        hover = fig.data[0].hovertext
        assert all("FM Radio" not in h for h in hover)
        # Verify base hover text still works
        assert all("MHz" in h for h in hover)

    def test_waterfall_customdata_present(self, bins_fm, sample_table):
        from rtl_spectrum.plotting import plot_waterfall
        sweeps = [("12:00:00", bins_fm)]
        fig = plot_waterfall(
            sweeps=sweeps,
            show=False,
            bands=sample_table,
        )
        # Heatmap should have customdata set
        assert fig.data[0].customdata is not None
        # Should contain FM Radio annotation
        flat = str(fig.data[0].customdata)
        assert "FM Radio" in flat

    def test_waterfall_no_bands_no_customdata(self, bins_fm):
        from rtl_spectrum.plotting import plot_waterfall
        sweeps = [("12:00:00", bins_fm)]
        fig = plot_waterfall(
            sweeps=sweeps,
            show=False,
            bands=None,
        )
        assert fig.data[0].customdata is None

    def test_envelope_hover_contains_band(self, bins_fm, sample_table):
        from rtl_spectrum.plotting import plot_envelope
        fig = plot_envelope(
            min_series=bins_fm,
            max_series=bins_fm,
            avg_series=bins_fm,
            show=False,
            bands=sample_table,
        )
        # All three traces should have band annotations
        for trace in fig.data:
            hover = trace.hovertext
            assert any("FM Radio" in h for h in hover)

    def test_envelope_no_bands_clean(self, bins_fm):
        from rtl_spectrum.plotting import plot_envelope
        fig = plot_envelope(
            min_series=bins_fm,
            max_series=bins_fm,
            avg_series=bins_fm,
            show=False,
            bands=None,
        )
        for trace in fig.data:
            hover = trace.hovertext
            assert all("FM Radio" not in h for h in hover)


# ---------------------------------------------------------------------------
# TestOverlappingBands
# ---------------------------------------------------------------------------

class TestOverlappingBands:
    """Test behaviour with overlapping band allocations."""

    @pytest.fixture
    def overlapping_yaml(self, tmp_path):
        yaml_text = textwrap.dedent("""\
            - primary_service_category: WIDE SERVICE
              primary_frequency_range:
              - 100000.0
              - 200000.0
              subbands:
              - frequency_range:
                - 100000.0
                - 200000.0
                width: 100000.0
                usage: Wide usage
                technical_parameters:
                  mode_of_traffic: ''
              - frequency_range:
                - 120000.0
                - 130000.0
                width: 10000.0
                usage: Narrow usage
                technical_parameters:
                  mode_of_traffic: ''
        """)
        p = tmp_path / "overlap.yaml"
        p.write_text(yaml_text, encoding="utf-8")
        return p

    def test_narrowest_wins(self, overlapping_yaml):
        """When freq is in both wide and narrow band, narrow wins."""
        table = load_bands(overlapping_yaml)
        info = lookup_band(125_000_000, table)
        assert info is not None
        assert info.usage == "Narrow usage"

    def test_outside_narrow_gets_wide(self, overlapping_yaml):
        """When freq is in wide but not narrow, wide is returned."""
        table = load_bands(overlapping_yaml)
        info = lookup_band(150_000_000, table)
        assert info is not None
        assert info.usage == "Wide usage"


# ---------------------------------------------------------------------------
# TestValidateBandsYaml
# ---------------------------------------------------------------------------

class TestValidateBandsYaml:
    """Tests for validate_bands_yaml."""

    def test_valid_data_passes(self):
        """Well-formed data does not raise."""
        data = [
            {
                "primary_service_category": "BROADCASTING",
                "primary_frequency_range": [87500.0, 108000.0],
                "subbands": [
                    {
                        "frequency_range": [87500.0, 108000.0],
                        "width": 20500.0,
                        "usage": "FM Radio",
                    }
                ],
            }
        ]
        # Should not raise
        validate_bands_yaml(data)

    def test_not_a_list_raises(self):
        """Top-level dict instead of list."""
        with pytest.raises(ValueError, match="expected a list"):
            validate_bands_yaml({"key": "value"})

    def test_string_raises(self):
        """Top-level string instead of list."""
        with pytest.raises(ValueError, match="expected a list"):
            validate_bands_yaml("not a list")

    def test_none_raises(self):
        """None (empty YAML file)."""
        with pytest.raises(ValueError, match="expected a list"):
            validate_bands_yaml(None)

    def test_empty_list_raises(self):
        """Empty list."""
        with pytest.raises(ValueError, match="empty list"):
            validate_bands_yaml([])

    def test_entry_not_dict_raises(self):
        """Entry is a string, not a mapping."""
        with pytest.raises(ValueError, match="not a mapping"):
            validate_bands_yaml(["just a string"])

    def test_missing_primary_service_category(self):
        with pytest.raises(ValueError, match="primary_service_category"):
            validate_bands_yaml([
                {
                    "primary_frequency_range": [100.0, 200.0],
                    "subbands": [],
                }
            ])

    def test_empty_primary_service_category(self):
        with pytest.raises(ValueError, match="primary_service_category"):
            validate_bands_yaml([
                {
                    "primary_service_category": "",
                    "primary_frequency_range": [100.0, 200.0],
                    "subbands": [],
                }
            ])

    def test_missing_primary_frequency_range(self):
        with pytest.raises(ValueError, match="primary_frequency_range"):
            validate_bands_yaml([
                {
                    "primary_service_category": "TEST",
                    "subbands": [],
                }
            ])

    def test_primary_frequency_range_wrong_length(self):
        with pytest.raises(ValueError, match="exactly 2 numbers"):
            validate_bands_yaml([
                {
                    "primary_service_category": "TEST",
                    "primary_frequency_range": [100.0],
                    "subbands": [],
                }
            ])

    def test_primary_frequency_range_three_elements(self):
        with pytest.raises(ValueError, match="exactly 2 numbers"):
            validate_bands_yaml([
                {
                    "primary_service_category": "TEST",
                    "primary_frequency_range": [100.0, 200.0, 300.0],
                    "subbands": [],
                }
            ])

    def test_primary_frequency_range_non_numeric(self):
        with pytest.raises(ValueError, match="not a number"):
            validate_bands_yaml([
                {
                    "primary_service_category": "TEST",
                    "primary_frequency_range": ["abc", 200.0],
                    "subbands": [],
                }
            ])

    def test_missing_subbands(self):
        with pytest.raises(ValueError, match="subbands"):
            validate_bands_yaml([
                {
                    "primary_service_category": "TEST",
                    "primary_frequency_range": [100.0, 200.0],
                }
            ])

    def test_subbands_not_a_list(self):
        with pytest.raises(ValueError, match="subbands.*must be a list"):
            validate_bands_yaml([
                {
                    "primary_service_category": "TEST",
                    "primary_frequency_range": [100.0, 200.0],
                    "subbands": "not a list",
                }
            ])

    def test_multiple_entries_valid(self):
        """Multiple valid entries should not raise."""
        data = [
            {
                "primary_service_category": "SERVICE_A",
                "primary_frequency_range": [100.0, 200.0],
                "subbands": [],
            },
            {
                "primary_service_category": "SERVICE_B",
                "primary_frequency_range": [200.0, 300.0],
                "subbands": [],
            },
        ]
        validate_bands_yaml(data)

    def test_error_in_second_entry(self):
        """First entry valid, second entry malformed."""
        data = [
            {
                "primary_service_category": "SERVICE_A",
                "primary_frequency_range": [100.0, 200.0],
                "subbands": [],
            },
            {
                "primary_service_category": "SERVICE_B",
                # missing primary_frequency_range
                "subbands": [],
            },
        ]
        with pytest.raises(ValueError, match="entry 1"):
            validate_bands_yaml(data)


# ---------------------------------------------------------------------------
# TestLoadBandsValidation
# ---------------------------------------------------------------------------

class TestLoadBandsValidation:
    """Test that load_bands surfaces validation errors for malformed files."""

    def test_load_malformed_not_list(self, tmp_path):
        """YAML file whose top-level is a dict."""
        p = tmp_path / "bad.yaml"
        p.write_text("key: value\n", encoding="utf-8")
        with pytest.raises(ValueError, match="expected a list"):
            load_bands(p)

    def test_load_malformed_missing_key(self, tmp_path):
        """YAML list entry missing required keys."""
        yaml_text = textwrap.dedent("""\
            - name: something
              data: 123
        """)
        p = tmp_path / "bad2.yaml"
        p.write_text(yaml_text, encoding="utf-8")
        with pytest.raises(ValueError, match="primary_service_category"):
            load_bands(p)

    def test_load_empty_list(self, tmp_path):
        """YAML file with an empty list."""
        p = tmp_path / "empty.yaml"
        p.write_text("[]\n", encoding="utf-8")
        with pytest.raises(ValueError, match="empty list"):
            load_bands(p)


# ---------------------------------------------------------------------------
# TestDefaultYaml
# ---------------------------------------------------------------------------

class TestDefaultYaml:
    """Tests for the bundled default.yaml sample file."""

    @pytest.mark.skipif(not has_default, reason="default.yaml not present")
    def test_default_yaml_loads(self):
        """default.yaml should parse and produce a valid BandTable."""
        table = load_bands(DEFAULT_YAML)
        assert len(table.bands) > 0

    @pytest.mark.skipif(not has_default, reason="default.yaml not present")
    def test_default_yaml_contains_fm(self):
        """default.yaml should include FM Radio as a demo band."""
        table = load_bands(DEFAULT_YAML)
        usages = [b.usage for b in table.bands]
        assert any("FM" in u for u in usages)

    @pytest.mark.skipif(not has_default, reason="default.yaml not present")
    def test_default_yaml_sorted(self):
        """Bands should be sorted by start frequency."""
        table = load_bands(DEFAULT_YAML)
        starts = [b.start_hz for b in table.bands]
        assert starts == sorted(starts)

    @pytest.mark.skipif(not has_default, reason="default.yaml not present")
    def test_default_yaml_all_positive_ranges(self):
        """Every band must have start_hz < end_hz."""
        table = load_bands(DEFAULT_YAML)
        for b in table.bands:
            assert b.start_hz < b.end_hz, f"{b.usage}: {b.start_hz} >= {b.end_hz}"
