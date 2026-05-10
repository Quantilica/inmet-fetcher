"""Integration tests for CLI subcommands via main_cli()."""

import sys
from unittest.mock import patch

import httpx
import pandas as pd
import pytest

from inmet_bdmep.cli import main_cli
from inmet_bdmep.storage import InmetRepository
from tests.conftest import DEFAULT_DATA_ROWS, make_zip_bytes

FAKE_LAST_MODIFIED = "Mon, 01 Jan 2024 00:00:00 GMT"
FAKE_CONTENT = b"PK" + b"\x00" * 200


def cli(*args):
    with patch("sys.argv", ["inmet", *[str(a) for a in args]]):
        main_cli()


class TestFetchCLI:
    def test_fetch_downloads_file(self, tmp_path, httpx_mock):
        from inmet_bdmep.fetch import _build_url

        httpx_mock.add_response(
            method="HEAD",
            url=_build_url(2023),
            headers={
                "Last-Modified": FAKE_LAST_MODIFIED,
                "Content-Length": str(len(FAKE_CONTENT)),
            },
        )
        httpx_mock.add_response(
            method="GET",
            url=_build_url(2023),
            content=FAKE_CONTENT,
        )

        cli("fetch", "2023", "--data-dir", tmp_path)
        repo = InmetRepository(tmp_path)
        assert repo.path_for_year(2023, "2023.zip").exists()

    def test_fetch_workers_flag(self, tmp_path, httpx_mock):
        from inmet_bdmep.fetch import _build_url

        for year in [2022, 2023]:
            httpx_mock.add_response(
                method="HEAD",
                url=_build_url(year),
                headers={
                    "Last-Modified": FAKE_LAST_MODIFIED,
                    "Content-Length": str(len(FAKE_CONTENT)),
                },
            )
            httpx_mock.add_response(
                method="GET",
                url=_build_url(year),
                content=FAKE_CONTENT,
            )

        cli("fetch", "2022:2023", "--data-dir", tmp_path, "--workers", "2")
        repo = InmetRepository(tmp_path)
        assert repo.path_for_year(2022, "2022.zip").exists()
        assert repo.path_for_year(2023, "2023.zip").exists()


class TestReadCLI:
    def test_read_outputs_parquet(self, tmp_path, sample_zip_path):
        output = tmp_path / "out.parquet"
        cli(
            "read",
            "--data-dir",
            sample_zip_path.parent,
            "--output",
            output,
            "--format",
            "parquet",
        )
        assert output.exists()
        df = pd.read_parquet(output)
        assert len(df) > 0

    def test_read_outputs_csv(self, tmp_path, sample_zip_path):
        output = tmp_path / "out.csv"
        cli(
            "read",
            "--data-dir",
            sample_zip_path.parent,
            "--output",
            output,
            "--format",
            "csv",
        )
        assert output.exists()
        df = pd.read_csv(output)
        assert len(df) > 0

    def test_read_outputs_json(self, tmp_path, sample_zip_path):
        output = tmp_path / "out.json"
        cli(
            "read",
            "--data-dir",
            sample_zip_path.parent,
            "--output",
            output,
            "--format",
            "json",
        )
        assert output.exists()

    def test_read_filter_uf(self, tmp_path, multi_station_zip_bytes):
        zip_path = tmp_path / "inmet-bdmep_2023_20240101.zip"
        zip_path.write_bytes(multi_station_zip_bytes)
        output = tmp_path / "out.parquet"
        cli("read", "--data-dir", tmp_path, "--uf", "SP", "--output", output)
        df = pd.read_parquet(output)
        assert set(df["uf"].unique()) == {"SP"}

    def test_read_filter_station(self, tmp_path, multi_station_zip_bytes):
        zip_path = tmp_path / "inmet-bdmep_2023_20240101.zip"
        zip_path.write_bytes(multi_station_zip_bytes)
        output = tmp_path / "out.parquet"
        cli("read", "--data-dir", tmp_path, "--station", "C001", "--output", output)
        df = pd.read_parquet(output)
        assert set(df["codigo_wmo"].unique()) == {"C001"}

    def test_read_filter_date_range(self, tmp_path, sample_zip_path):
        output = tmp_path / "out.parquet"
        cli(
            "read",
            "--data-dir",
            sample_zip_path.parent,
            "--start",
            "2023-01-02",
            "--end",
            "2023-01-02",
            "--output",
            output,
        )
        df = pd.read_parquet(output)
        assert all(df["data_hora"] >= pd.Timestamp("2023-01-02"))

    def test_read_filter_years(self, tmp_path, make_zip):
        for year in [2021, 2022, 2023]:
            (tmp_path / f"inmet-bdmep_{year}_20240101.zip").write_bytes(
                make_zip((f"A001_{year}.CSV", {"codigo_wmo": "A001"}))
            )
        output = tmp_path / "out.parquet"
        cli("read", "--data-dir", tmp_path, "--years", "2022", "--output", output)
        df = pd.read_parquet(output)
        assert len(df) == len(DEFAULT_DATA_ROWS)

    def test_read_no_data_prints_message(self, tmp_path, sample_zip_path, capsys):
        cli("read", "--data-dir", sample_zip_path.parent, "--uf", "ZZ")
        out = capsys.readouterr().out
        assert "Nenhum dado encontrado" in out


class TestStationsCLI:
    def test_stations_outputs_csv(self, tmp_path, sample_zip_path):
        output = tmp_path / "stations.csv"
        cli("stations", "--data-dir", sample_zip_path.parent, "--output", output)
        assert output.exists()
        df = pd.read_csv(output)
        assert "codigo_wmo" in df.columns
        assert len(df) >= 1

    def test_stations_outputs_parquet(self, tmp_path, sample_zip_path):
        output = tmp_path / "stations.parquet"
        cli(
            "stations",
            "--data-dir",
            sample_zip_path.parent,
            "--output",
            output,
            "--format",
            "parquet",
        )
        assert output.exists()
        df = pd.read_parquet(output)
        assert "codigo_wmo" in df.columns

    def test_stations_multiple(self, tmp_path, multi_station_zip_bytes):
        (tmp_path / "inmet-bdmep_2023_20240101.zip").write_bytes(
            multi_station_zip_bytes
        )
        output = tmp_path / "stations.csv"
        cli("stations", "--data-dir", tmp_path, "--output", output)
        df = pd.read_csv(output)
        assert set(df["codigo_wmo"].tolist()) == {"A001", "B001", "C001"}

    def test_stations_year_filter(self, tmp_path, make_zip):
        (tmp_path / "inmet-bdmep_2022_20240101.zip").write_bytes(
            make_zip(("A001.CSV", {"codigo_wmo": "A001"}))
        )
        (tmp_path / "inmet-bdmep_2023_20240101.zip").write_bytes(
            make_zip(("B001.CSV", {"codigo_wmo": "B001"}))
        )
        output = tmp_path / "stations.csv"
        cli("stations", "--data-dir", tmp_path, "--years", "2023", "--output", output)
        df = pd.read_csv(output)
        assert set(df["codigo_wmo"].tolist()) == {"B001"}

    def test_stations_no_output_prints(self, tmp_path, sample_zip_path, capsys):
        cli("stations", "--data-dir", sample_zip_path.parent)
        out = capsys.readouterr().out
        assert "A001" in out
