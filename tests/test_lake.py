"""Tests for Hive lake conversion of INMET BDMEP data."""

from __future__ import annotations

import zipfile
from importlib.metadata import entry_points
from pathlib import Path

import pytest

pytest.importorskip("quantilica.analytics.lake")
pytest.importorskip("duckdb")

from quantilica.analytics.lake import check_dataset, scan_dataset  # noqa: E402
from typer.testing import CliRunner  # noqa: E402

from inmet_fetcher.lake import (  # noqa: E402
    DATASET_ID,
    SOURCE_ID,
    converter,
    year_from_path,
)
from inmet_fetcher.plugin import app  # noqa: E402

FIXTURE_CSV_2015 = (
    Path(__file__).parent
    / "fixtures"
    / "INMET_CO_DF_A001_BRASILIA_01-01-2015_A_31-12-2015.CSV"
)


def test_entry_point_registered() -> None:
    eps = entry_points(group="quantilica.lake")
    matches = [ep for ep in eps if ep.name == "inmet"]
    assert len(matches) == 1
    loaded = matches[0].load()
    assert loaded is converter
    assert loaded.source_id == SOURCE_ID


def test_year_from_path() -> None:
    assert year_from_path(Path("2015.zip")) == "2015"
    assert year_from_path(Path("bdmep-2022@20221021.zip")) == "2022"
    assert year_from_path(Path("2020/stations.zip")) == "2020"
    assert year_from_path(Path("unknown.zip")) is None


def test_converter_datasets() -> None:
    assert converter.datasets() == [DATASET_ID]


def test_convert_end_to_end(tmp_path: Path) -> None:
    if not FIXTURE_CSV_2015.exists():
        pytest.skip("Fixture 2015 não encontrada")

    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    # Create a 2015.zip with the fixture CSV
    zip_path = raw_dir / "2015.zip"
    with zipfile.ZipFile(zip_path, "w") as z:
        z.write(FIXTURE_CSV_2015, arcname=FIXTURE_CSV_2015.name)

    lake_dir = tmp_path / "lake"
    res = converter.convert(raw_dir, lake_dir)
    assert not res.errors, res.errors
    assert res.converted == 1
    assert res.skipped == 0

    dataset_dir = lake_dir / SOURCE_ID / DATASET_ID
    assert check_dataset(dataset_dir) == []

    df = scan_dataset(dataset_dir).collect()
    assert df.height > 0
    assert "ano" in df.columns
    assert df["ano"][0] == "2015"
    assert "temperatura_ar" in df.columns

    # Second run skips
    res2 = converter.convert(raw_dir, lake_dir)
    assert not res2.errors
    assert res2.converted == 0
    assert res2.skipped == 1


def test_cli_convert(tmp_path: Path) -> None:
    if not FIXTURE_CSV_2015.exists():
        pytest.skip("Fixture 2015 não encontrada")

    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    zip_path = raw_dir / "2015.zip"
    with zipfile.ZipFile(zip_path, "w") as z:
        z.write(FIXTURE_CSV_2015, arcname=FIXTURE_CSV_2015.name)

    lake_dir = tmp_path / "lake"
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["convert", "-i", str(raw_dir), "--lake", str(lake_dir)],
    )
    assert result.exit_code == 0, result.output
    assert (lake_dir / SOURCE_ID / DATASET_ID).exists()
