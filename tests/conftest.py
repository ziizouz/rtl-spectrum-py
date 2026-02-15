"""Shared test fixtures and helpers for rtl_spectrum tests."""

from pathlib import Path

import pytest

# Root directory for test resource files
RESOURCES_DIR = Path(__file__).parent / "resources"


@pytest.fixture
def resources_dir() -> Path:
    """Return the path to the test resources directory."""
    return RESOURCES_DIR


@pytest.fixture
def test_csv(resources_dir: Path) -> Path:
    """Return the path to test.csv."""
    return resources_dir / "test.csv"


@pytest.fixture
def subtract_csv(resources_dir: Path) -> Path:
    """Return the path to subtract.csv."""
    return resources_dir / "subtract.csv"


@pytest.fixture
def validation_csv(resources_dir: Path) -> Path:
    """Return the path to test_validation.csv."""
    return resources_dir / "test_validation.csv"
