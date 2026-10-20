"""Reader tests on real INMET station files and on the failure modes they show.

``tests/fixtures`` holds the head of two real station files, unchanged
(Latin-1, original header and line endings):

- ``..._A001_BRASILIA_..._2015``: layout up to 2018 (``AAAA-MM-DD``, ``HH:MM``,
  missing values as ``-9999``, headers without some accents, ``,5``);
- ``..._A438_MARAU_..._2022``: layout from 2019 (``AAAA/MM/DD``, ``HHMM UTC``,
  missing values as empty fields), with 233 hours fully empty before the
  first value written without the leading zero (``,2``).
"""

import datetime as dt
import io
import zipfile
from pathlib import Path

import polars as pl
import pytest

from inmet_fetcher.reader import (
    _MEASURE_COLS,
    find_zipfiles,
    read,
    read_metadata,
    read_station_data,
    read_zipfile,
)
from tests.conftest import DEFAULT_DATA_ROWS, make_station_csv

FIXTURES = Path(__file__).parent / "fixtures"
OLD = FIXTURES / "INMET_CO_DF_A001_BRASILIA_01-01-2015_A_31-12-2015.CSV"
NEW = FIXTURES / "INMET_NE_BA_A438_MARAU_01-01-2022_A_31-12-2022.CSV"


def _zip(path: Path, members: dict[str, bytes]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in members.items():
            z.writestr(name, data)
    return path


class TestRealFiles:
    def test_old_layout_values(self):
        df = read_station_data(OLD.read_bytes())
        first = df.row(0, named=True)

        assert df.columns == [*_MEASURE_COLS, "data_hora"]
        assert first["data_hora"] == dt.datetime(2015, 1, 1, 0, 0, tzinfo=dt.UTC)
        assert first["pressao_atmosferica"] == pytest.approx(886.8)
        assert first["radiacao"] is None  # -9999
        assert first["temperatura_ar"] == pytest.approx(20.1)
        assert first["vento_velocidade"] == pytest.approx(0.5)  # ",5"
        assert all(df.schema[c] == pl.Float64 for c in _MEASURE_COLS)

    def test_new_layout_with_leading_empty_hours_and_comma_without_zero(self):
        df = read_station_data(NEW.read_bytes(), drop_empty=False)

        assert df.height == len(NEW.read_bytes().splitlines()) - 9
        assert df["data_hora"][0] == dt.datetime(2022, 1, 1, 0, 0, tzinfo=dt.UTC)
        empty = df.filter(pl.all_horizontal(pl.col(c).is_null() for c in _MEASURE_COLS))
        assert empty.height >= 233
        values = df.unpivot(on=_MEASURE_COLS)["value"].drop_nulls().abs()
        assert ((values > 0) & (values < 1)).any()  # ",2" lido como 0.2

    def test_drop_empty_removes_only_fully_empty_hours(self):
        all_rows = read_station_data(NEW.read_bytes(), drop_empty=False)
        kept = read_station_data(NEW.read_bytes())
        empty = all_rows.filter(
            pl.all_horizontal(pl.col(c).is_null() for c in _MEASURE_COLS)
        )
        assert kept.height == all_rows.height - empty.height

    def test_metadata_from_zip_member_keeps_accents(self, tmp_path):
        path = _zip(tmp_path / "x.zip", {OLD.name: OLD.read_bytes()})
        with zipfile.ZipFile(path) as z:
            meta = read_metadata(z.open(OLD.name))
        assert meta["codigo_wmo"] == "A001"
        assert meta["estacao"] == "BRASILIA"
        assert meta["latitude"] == pytest.approx(-15.78944444)
        assert meta["data_fundacao"] == dt.datetime(2000, 5, 7)

    def test_zip_member_read_like_bytes(self, tmp_path):
        path = _zip(
            tmp_path / "bdmep" / "2015" / "inmet-bdmep_2015@20160101.zip",
            {f"2015/{OLD.name}": OLD.read_bytes()},
        )
        df = read_zipfile(path)
        assert df.height == read_station_data(OLD.read_bytes()).height
        assert set(df["codigo_wmo"]) == {"A001"}


class TestStrictness:
    def test_non_numeric_value_raises(self):
        rows = [DEFAULT_DATA_ROWS[0].replace(";28,5;", ";28,5x;")]
        with pytest.raises(ValueError, match="não numéricos"):
            read_station_data(make_station_csv(data_rows=rows))

    def test_unknown_header_raises(self):
        data = make_station_csv().replace(b"RADIA\xc7\xc3O GLOBAL", b"OUTRA COISA")
        with pytest.raises(ValueError, match="não reconhecidos"):
            read_station_data(data)

    def test_extra_field_raises(self):
        # O campo a mais cai na coluna sem nome do ";" final, que deve vir vazia.
        rows = [DEFAULT_DATA_ROWS[0] + "99;"]
        with pytest.raises((ValueError, pl.exceptions.PolarsError)):
            read_station_data(make_station_csv(data_rows=rows))

    def test_invalid_hour_raises(self):
        rows = [DEFAULT_DATA_ROWS[0].replace("0000 UTC", "2500 UTC")]
        with pytest.raises(pl.exceptions.PolarsError):
            read_station_data(make_station_csv(data_rows=rows))

    def test_file_object_is_decoded_as_latin1(self):
        df = read_station_data(io.BytesIO(make_station_csv()))
        assert df.height == len(DEFAULT_DATA_ROWS)


class TestDuplicateExtracts:
    def test_keeps_the_extract_that_ends_last(self, tmp_path):
        early = make_station_csv(data_rows=DEFAULT_DATA_ROWS[:2])
        late = make_station_csv(data_rows=DEFAULT_DATA_ROWS)
        path = _zip(
            tmp_path / "2026.zip",
            {
                "INMET_N_AM_A001_TESTE_01-01-2026_A_31-08-2026.CSV": early,
                "INMET_N_AM_A001_TESTE_01-01-2026_A_30-09-2026.CSV": late,
            },
        )
        df = read_zipfile(path)
        assert df.height == len(DEFAULT_DATA_ROWS)

    def test_same_station_without_distinct_period_raises(self, tmp_path):
        path = _zip(
            tmp_path / "x.zip",
            {"A001_a.CSV": make_station_csv(), "A001_b.CSV": make_station_csv()},
        )
        with pytest.raises(ValueError, match="sem período distinto"):
            read_zipfile(path)


class TestVersionsOfTheSameYear:
    def _write(self, root: Path, stamp: str, rows: list[str]) -> None:
        _zip(
            root / "bdmep" / "2025" / f"inmet-bdmep_2025@{stamp}.zip",
            {"A001_2025.CSV": make_station_csv(data_rows=rows)},
        )

    def test_find_zipfiles_returns_latest_version_per_year(self, tmp_path):
        self._write(tmp_path, "20251001", DEFAULT_DATA_ROWS[:1])
        self._write(tmp_path, "20251104", DEFAULT_DATA_ROWS)
        result = find_zipfiles(tmp_path)
        assert [p.name for p in result] == ["inmet-bdmep_2025@20251104.zip"]
        assert len(find_zipfiles(tmp_path, latest_only=False)) == 2

    def test_read_does_not_repeat_hours_across_versions(self, tmp_path):
        self._write(tmp_path, "20251001", DEFAULT_DATA_ROWS[:1])
        self._write(tmp_path, "20251104", DEFAULT_DATA_ROWS)
        df = read(tmp_path)
        assert df.height == len(DEFAULT_DATA_ROWS)
