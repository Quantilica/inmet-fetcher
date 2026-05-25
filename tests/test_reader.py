"""Tests for read_metadata, read_station_data, read_zipfile, find_zipfiles, read, read_stations."""

import datetime as dt
import io
import zipfile

import polars as pl
import pytest

from inmet_fetcher.reader import (
    find_zipfiles,
    read,
    read_metadata,
    read_station_data,
    read_stations,
    read_zipfile,
)
from tests.conftest import (
    ALL_NULL_ROW,
    CSV_HEADER,
    DEFAULT_DATA_ROWS,
    make_station_csv,
    make_zip_bytes,
)

# ─── helpers ────────────────────────────────────────────────────────────────


def open_zip_member(zip_bytes: bytes, filename: str):
    buf = io.BytesIO(zip_bytes)
    z = zipfile.ZipFile(buf)
    return z, z.open(filename)


# ─── read_metadata ──────────────────────────────────────────────────────────


class TestReadMetadata:
    def test_basic_fields_from_zipfile(self, sample_zip_bytes):
        buf = io.BytesIO(sample_zip_bytes)
        with zipfile.ZipFile(buf) as z:
            filename = [f for f in z.namelist() if not f.endswith("/")][0]
            meta = read_metadata(z.open(filename))

        assert meta["regiao"] == "Norte"
        assert meta["uf"] == "AM"
        assert meta["estacao"] == "Estação Teste"
        assert meta["codigo_wmo"] == "A001"

    def test_coordinates_parsed_as_float(self, sample_zip_bytes):
        buf = io.BytesIO(sample_zip_bytes)
        with zipfile.ZipFile(buf) as z:
            filename = z.namelist()[0]
            meta = read_metadata(z.open(filename))

        assert isinstance(meta["latitude"], float)
        assert isinstance(meta["longitude"], float)
        assert isinstance(meta["altitude"], float)
        assert meta["latitude"] == pytest.approx(-3.103)
        assert meta["longitude"] == pytest.approx(-60.016)
        assert meta["altitude"] == pytest.approx(48.0)

    def test_invalid_coordinate_returns_none(self, tmp_path):
        csv_bytes = make_station_csv(latitude="N/D", longitude="N/D")
        path = tmp_path / "test.csv"
        path.write_bytes(csv_bytes)
        meta = read_metadata(path)
        assert meta["latitude"] is None
        assert meta["longitude"] is None

    def test_date_iso_format(self, tmp_path):
        csv_bytes = make_station_csv(data_fundacao="1990-06-15")
        path = tmp_path / "test.csv"
        path.write_bytes(csv_bytes)
        meta = read_metadata(path)
        assert meta["data_fundacao"] == dt.datetime(1990, 6, 15)

    def test_date_slash_format(self, tmp_path):
        csv_bytes = make_station_csv(data_fundacao="15/06/90")
        path = tmp_path / "test.csv"
        path.write_bytes(csv_bytes)
        meta = read_metadata(path)
        assert meta["data_fundacao"] == dt.datetime(1990, 6, 15)

    def test_from_path(self, tmp_path):
        csv_bytes = make_station_csv(uf="SP", codigo_wmo="B001")
        path = tmp_path / "station.csv"
        path.write_bytes(csv_bytes)
        meta = read_metadata(path)
        assert meta["uf"] == "SP"
        assert meta["codigo_wmo"] == "B001"


# ─── read_station_data ──────────────────────────────────────────────────────


class TestReadStationData:
    def _make_file(self, **kwargs):
        return io.BytesIO(make_station_csv(**kwargs))

    def test_returns_dataframe(self):
        df = read_station_data(self._make_file())
        assert isinstance(df, pl.DataFrame)

    def test_expected_columns(self):
        df = read_station_data(self._make_file())
        assert "data_hora" in df.columns
        assert "temperatura_ar" in df.columns
        assert "precipitacao" in df.columns
        assert "data" not in df.columns
        assert "hora" not in df.columns

    def test_row_count(self):
        df = read_station_data(self._make_file())
        assert len(df) == len(DEFAULT_DATA_ROWS)

    def test_datetime_column_type(self):
        df = read_station_data(self._make_file())
        assert df["data_hora"].dtype == pl.Datetime

    def test_datetime_values(self):
        df = read_station_data(self._make_file())
        assert df["data_hora"][0] == dt.datetime(2023, 1, 1, 0, 0)
        assert df["data_hora"][1] == dt.datetime(2023, 1, 1, 1, 0)
        assert df["data_hora"][2] == dt.datetime(2023, 1, 2, 0, 0)

    def test_decimal_comma_parsed(self):
        df = read_station_data(self._make_file())
        assert df["temperatura_ar"][0] == pytest.approx(28.5)
        assert df["precipitacao"][1] == pytest.approx(0.2)

    def test_na_values_parsed(self):
        rows = [
            "2023-01-01;0000 UTC;-9999;1013,2;1013,5;1012,8;100,0;-9999;24,0;29,0;28,0;25,0;23,5;85;80;82;180;5,2;3,1;"
        ]
        df = read_station_data(self._make_file(data_rows=rows))
        assert df["precipitacao"][0] is None
        assert df["temperatura_ar"][0] is None

    def test_all_null_rows_filtered(self):
        rows = DEFAULT_DATA_ROWS + [ALL_NULL_ROW]
        df = read_station_data(self._make_file(data_rows=rows))
        assert len(df) == len(DEFAULT_DATA_ROWS)

    def test_slash_date_format(self):
        rows = [
            "2023/01/01;00:00;0,0;1013,2;1013,5;1012,8;100,0;28,5;24,0;29,0;28,0;25,0;23,5;85;80;82;180;5,2;3,1;"
        ]
        df = read_station_data(self._make_file(data_rows=rows))
        assert df["data_hora"][0] == dt.datetime(2023, 1, 1, 0, 0)


# ─── read_zipfile ───────────────────────────────────────────────────────────


class TestReadZipfile:
    def test_returns_dataframe(self, sample_zip_path):
        df = read_zipfile(sample_zip_path)
        assert isinstance(df, pl.DataFrame)
        assert len(df) > 0

    def test_metadata_attached(self, sample_zip_path):
        df = read_zipfile(sample_zip_path)
        assert "uf" in df.columns
        assert "codigo_wmo" in df.columns
        assert "latitude" in df.columns
        assert df["uf"][0] == "AM"
        assert df["codigo_wmo"][0] == "A001"

    def test_filter_uf_match(self, tmp_path, multi_station_zip_bytes):
        path = tmp_path / "inmet-bdmep_2023_20240101.zip"
        path.write_bytes(multi_station_zip_bytes)
        df = read_zipfile(path, uf=["SP"])
        assert set(df["uf"].to_list()) == {"SP"}

    def test_filter_uf_no_match(self, tmp_path, multi_station_zip_bytes):
        path = tmp_path / "inmet-bdmep_2023_20240101.zip"
        path.write_bytes(multi_station_zip_bytes)
        df = read_zipfile(path, uf=["RS"])
        assert len(df) == 0

    def test_filter_uf_multiple(self, tmp_path, multi_station_zip_bytes):
        path = tmp_path / "inmet-bdmep_2023_20240101.zip"
        path.write_bytes(multi_station_zip_bytes)
        df = read_zipfile(path, uf=["SP", "RJ"])
        assert set(df["uf"].to_list()) == {"SP", "RJ"}

    def test_filter_station_match(self, tmp_path, multi_station_zip_bytes):
        path = tmp_path / "inmet-bdmep_2023_20240101.zip"
        path.write_bytes(multi_station_zip_bytes)
        df = read_zipfile(path, station=["B001"])
        assert set(df["codigo_wmo"].to_list()) == {"B001"}

    def test_filter_station_no_match(self, tmp_path, multi_station_zip_bytes):
        path = tmp_path / "inmet-bdmep_2023_20240101.zip"
        path.write_bytes(multi_station_zip_bytes)
        df = read_zipfile(path, station=["Z999"])
        assert len(df) == 0

    def test_filter_start_date(self, sample_zip_path):
        df = read_zipfile(sample_zip_path, start="2023-01-02")
        assert (df["data_hora"] >= dt.datetime(2023, 1, 2)).all()

    def test_filter_end_date(self, sample_zip_path):
        df = read_zipfile(sample_zip_path, end="2023-01-01")
        assert (df["data_hora"] <= dt.datetime(2023, 1, 1, 23, 59, 59)).all()

    def test_filter_date_range(self, sample_zip_path):
        df = read_zipfile(
            sample_zip_path, start="2023-01-01 01:00", end="2023-01-01 01:00"
        )
        assert len(df) == 1
        assert df["data_hora"][0] == dt.datetime(2023, 1, 1, 1, 0)

    def test_filter_date_no_match_returns_empty(self, sample_zip_path):
        df = read_zipfile(sample_zip_path, start="2025-01-01")
        assert len(df) == 0

    def test_all_stations_loaded_without_filter(
        self, tmp_path, multi_station_zip_bytes
    ):
        path = tmp_path / "inmet-bdmep_2023_20240101.zip"
        path.write_bytes(multi_station_zip_bytes)
        df = read_zipfile(path)
        assert set(df["uf"].to_list()) == {"AM", "SP", "RJ"}


# ─── find_zipfiles ──────────────────────────────────────────────────────────


class TestFindZipfiles:
    @staticmethod
    def _make_zip(tmp_path, year: int, stamp: str = "20240101") -> None:
        year_dir = tmp_path / "bdmep" / str(year)
        year_dir.mkdir(parents=True, exist_ok=True)
        (year_dir / f"inmet-bdmep_{year}@{stamp}.zip").touch()

    def test_empty_dir(self, tmp_path):
        assert find_zipfiles(tmp_path) == []

    def test_finds_matching_files(self, tmp_path):
        self._make_zip(tmp_path, 2022, "20230101")
        self._make_zip(tmp_path, 2023, "20240101")
        result = find_zipfiles(tmp_path)
        assert len(result) == 2

    def test_ignores_non_matching_files(self, tmp_path):
        self._make_zip(tmp_path, 2023)
        (tmp_path / "other_file.zip").touch()
        (tmp_path / "readme.txt").touch()
        result = find_zipfiles(tmp_path)
        assert len(result) == 1

    def test_year_filter(self, tmp_path):
        for year in [2020, 2021, 2022, 2023]:
            self._make_zip(tmp_path, year)
        result = find_zipfiles(tmp_path, years=[2021, 2023])
        years_found = {int(p.parent.name) for p in result}
        assert years_found == {2021, 2023}

    def test_returns_sorted(self, tmp_path):
        for year in [2023, 2021, 2022]:
            self._make_zip(tmp_path, year)
        result = find_zipfiles(tmp_path)
        names = [p.name for p in result]
        assert names == sorted(names)


# ─── read ────────────────────────────────────────────────────────────────────


class TestRead:
    def test_raises_when_no_zips(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            read(tmp_path)

    def test_basic_read(self, tmp_path, sample_zip_path):
        df = read(tmp_path)
        assert isinstance(df, pl.DataFrame)
        assert len(df) > 0

    def _write_zip(self, tmp_path, year: int, zip_bytes: bytes) -> None:
        year_dir = tmp_path / "bdmep" / str(year)
        year_dir.mkdir(parents=True, exist_ok=True)
        (year_dir / f"inmet-bdmep_{year}@20240101.zip").write_bytes(zip_bytes)

    def test_year_filter(self, tmp_path, make_zip):
        for year in [2021, 2022, 2023]:
            self._write_zip(
                tmp_path,
                year,
                make_zip((f"A001_{year}.CSV", {"codigo_wmo": "A001"})),
            )
        df = read(tmp_path, years=[2022])
        assert len(df) == len(DEFAULT_DATA_ROWS)

    def test_uf_filter(self, tmp_path, multi_station_zip_bytes):
        self._write_zip(tmp_path, 2023, multi_station_zip_bytes)
        df = read(tmp_path, uf=["SP"])
        assert set(df["uf"].to_list()) == {"SP"}

    def test_station_filter(self, tmp_path, multi_station_zip_bytes):
        self._write_zip(tmp_path, 2023, multi_station_zip_bytes)
        df = read(tmp_path, station=["C001"])
        assert set(df["codigo_wmo"].to_list()) == {"C001"}

    def test_date_filter(self, tmp_path, sample_zip_path):
        df = read(tmp_path, start="2023-01-02", end="2023-01-02")
        assert (df["data_hora"] >= dt.datetime(2023, 1, 2)).all()
        assert (df["data_hora"] <= dt.datetime(2023, 1, 2, 23, 59)).all()

    def test_multi_year_concat(self, tmp_path, make_zip):
        for year in [2021, 2022]:
            self._write_zip(
                tmp_path,
                year,
                make_zip((f"A001_{year}.CSV", {"codigo_wmo": "A001"})),
            )
        df = read(tmp_path)
        assert len(df) == 2 * len(DEFAULT_DATA_ROWS)


# ─── read_stations ──────────────────────────────────────────────────────────


class TestReadStations:
    @staticmethod
    def _write_zip(tmp_path, year: int, zip_bytes: bytes) -> None:
        year_dir = tmp_path / "bdmep" / str(year)
        year_dir.mkdir(parents=True, exist_ok=True)
        (year_dir / f"inmet-bdmep_{year}@20240101.zip").write_bytes(zip_bytes)

    def test_raises_when_no_zips(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            read_stations(tmp_path)

    def test_returns_dataframe(self, tmp_path, sample_zip_path):
        df = read_stations(tmp_path)
        assert isinstance(df, pl.DataFrame)

    def test_expected_columns(self, tmp_path, sample_zip_path):
        df = read_stations(tmp_path)
        for col in ["codigo_wmo", "uf", "estacao", "latitude", "longitude", "altitude"]:
            assert col in df.columns

    def test_deduplication(self, tmp_path, make_zip):
        for year in [2022, 2023]:
            self._write_zip(
                tmp_path, year, make_zip(("A001.CSV", {"codigo_wmo": "A001"}))
            )
        df = read_stations(tmp_path)
        assert len(df.filter(pl.col("codigo_wmo") == "A001")) == 1

    def test_multiple_stations(self, tmp_path, multi_station_zip_bytes):
        self._write_zip(tmp_path, 2023, multi_station_zip_bytes)
        df = read_stations(tmp_path)
        assert set(df["codigo_wmo"].to_list()) == {"A001", "B001", "C001"}

    def test_sorted_by_codigo_wmo(self, tmp_path, multi_station_zip_bytes):
        self._write_zip(tmp_path, 2023, multi_station_zip_bytes)
        df = read_stations(tmp_path)
        codes = df["codigo_wmo"].to_list()
        assert codes == sorted(codes)

    def test_year_filter(self, tmp_path, make_zip):
        self._write_zip(
            tmp_path,
            2022,
            make_zip(("A001.CSV", {"codigo_wmo": "A001", "uf": "AM"})),
        )
        self._write_zip(
            tmp_path,
            2023,
            make_zip(("B001.CSV", {"codigo_wmo": "B001", "uf": "SP"})),
        )
        df = read_stations(tmp_path, years=[2022])
        assert set(df["codigo_wmo"].to_list()) == {"A001"}
