"""Integration tests for CLI subcommands via main_cli()."""

import sys
from unittest.mock import patch

import httpx
import pandas as pd
import pytest

from inmet_fetcher.cli import main_cli
from inmet_fetcher.storage import InmetRepository
from tests.conftest import DEFAULT_DATA_ROWS, make_zip_bytes

FAKE_LAST_MODIFIED = "Mon, 01 Jan 2024 00:00:00 GMT"
FAKE_CONTENT = b"PK" + b"\x00" * 200


def cli(*args):
    with patch("sys.argv", ["inmet", *[str(a) for a in args]]):
        main_cli()


class TestSyncCLI:
    def test_sync_downloads_file(self, tmp_path, httpx_mock):
        from inmet_fetcher.fetch import _build_url

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

        cli("sync", "2023", "-o", tmp_path)
        repo = InmetRepository(tmp_path)
        assert repo.path_for_year(2023, "2023.zip").exists()

    def test_sync_workers_flag(self, tmp_path, httpx_mock):
        from inmet_fetcher.fetch import _build_url

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

        cli("sync", "2022:2023", "-o", tmp_path, "--workers", "2")
        repo = InmetRepository(tmp_path)
        assert repo.path_for_year(2022, "2022.zip").exists()
        assert repo.path_for_year(2023, "2023.zip").exists()


class TestReadCLI:
    def test_read_outputs_parquet(self, tmp_path, sample_zip_path):
        output = tmp_path / "out.parquet"
        cli(
            "read",
            "-o",
            tmp_path,
            "--save-as",
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
            "-o",
            tmp_path,
            "--save-as",
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
            "-o",
            tmp_path,
            "--save-as",
            output,
            "--format",
            "json",
        )
        assert output.exists()

    def test_read_filter_uf(self, tmp_path, multi_station_zip_bytes):
        year_dir = tmp_path / "bdmep" / "2023"
        year_dir.mkdir(parents=True, exist_ok=True)
        (year_dir / "inmet-bdmep_2023@20240101.zip").write_bytes(
            multi_station_zip_bytes
        )
        output = tmp_path / "out.parquet"
        cli("read", "-o", tmp_path, "--uf", "SP", "--save-as", output)
        df = pd.read_parquet(output)
        assert set(df["uf"].unique()) == {"SP"}

    def test_read_filter_station(self, tmp_path, multi_station_zip_bytes):
        year_dir = tmp_path / "bdmep" / "2023"
        year_dir.mkdir(parents=True, exist_ok=True)
        (year_dir / "inmet-bdmep_2023@20240101.zip").write_bytes(
            multi_station_zip_bytes
        )
        output = tmp_path / "out.parquet"
        cli("read", "-o", tmp_path, "--station", "C001", "--save-as", output)
        df = pd.read_parquet(output)
        assert set(df["codigo_wmo"].unique()) == {"C001"}

    def test_read_filter_date_range(self, tmp_path, sample_zip_path):
        output = tmp_path / "out.parquet"
        cli(
            "read",
            "-o",
            tmp_path,
            "--start",
            "2023-01-02",
            "--end",
            "2023-01-02",
            "--save-as",
            output,
        )
        df = pd.read_parquet(output)
        assert all(df["data_hora"] >= pd.Timestamp("2023-01-02"))

    def test_read_filter_years(self, tmp_path, make_zip):
        for year in [2021, 2022, 2023]:
            year_dir = tmp_path / "bdmep" / str(year)
            year_dir.mkdir(parents=True, exist_ok=True)
            (year_dir / f"inmet-bdmep_{year}@20240101.zip").write_bytes(
                make_zip((f"A001_{year}.CSV", {"codigo_wmo": "A001"}))
            )
        output = tmp_path / "out.parquet"
        cli("read", "-o", tmp_path, "--years", "2022", "--save-as", output)
        df = pd.read_parquet(output)
        assert len(df) == len(DEFAULT_DATA_ROWS)

    def test_read_no_data_prints_message(self, tmp_path, sample_zip_path, capsys):
        cli("read", "-o", tmp_path, "--uf", "ZZ")
        out = capsys.readouterr().out
        assert "Nenhum dado encontrado" in out


class TestStationsCLI:
    def test_stations_outputs_csv(self, tmp_path, sample_zip_path):
        output = tmp_path / "stations.csv"
        cli("stations", "-o", tmp_path, "--save-as", output)
        assert output.exists()
        df = pd.read_csv(output)
        assert "codigo_wmo" in df.columns
        assert len(df) >= 1

    def test_stations_outputs_parquet(self, tmp_path, sample_zip_path):
        output = tmp_path / "stations.parquet"
        cli(
            "stations",
            "-o",
            tmp_path,
            "--save-as",
            output,
            "--format",
            "parquet",
        )
        assert output.exists()
        df = pd.read_parquet(output)
        assert "codigo_wmo" in df.columns

    def test_stations_multiple(self, tmp_path, multi_station_zip_bytes):
        year_dir = tmp_path / "bdmep" / "2023"
        year_dir.mkdir(parents=True, exist_ok=True)
        (year_dir / "inmet-bdmep_2023@20240101.zip").write_bytes(
            multi_station_zip_bytes
        )
        output = tmp_path / "stations.csv"
        cli("stations", "-o", tmp_path, "--save-as", output)
        df = pd.read_csv(output)
        assert set(df["codigo_wmo"].tolist()) == {"A001", "B001", "C001"}

    def test_stations_year_filter(self, tmp_path, make_zip):
        for year, station in [(2022, "A001"), (2023, "B001")]:
            year_dir = tmp_path / "bdmep" / str(year)
            year_dir.mkdir(parents=True, exist_ok=True)
            (year_dir / f"inmet-bdmep_{year}@20240101.zip").write_bytes(
                make_zip((f"{station}.CSV", {"codigo_wmo": station}))
            )
        output = tmp_path / "stations.csv"
        cli("stations", "-o", tmp_path, "--years", "2023", "--save-as", output)
        df = pd.read_csv(output)
        assert set(df["codigo_wmo"].tolist()) == {"B001"}

    def test_stations_no_output_prints(self, tmp_path, sample_zip_path, capsys):
        cli("stations", "-o", tmp_path)
        out = capsys.readouterr().out
        assert "A001" in out
