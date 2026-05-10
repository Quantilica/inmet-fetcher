"""Unit tests for pure utility functions."""

import datetime as dt

import numpy as np
import pytest

from inmet_bdmep.fetch import (
    _build_filename,
    _build_url,
    _parse_last_modified,
    expand_years,
)
from inmet_bdmep.reader import (
    _fix_hora,
    _parse_float,
    _rename_col,
)


class TestExpandYears:
    def test_single_year(self):
        assert expand_years("2023") == [2023]

    def test_range(self):
        assert expand_years("2020:2023") == [2020, 2021, 2022, 2023]

    def test_multiple_singles(self):
        assert expand_years("2020", "2022", "2024") == [2020, 2022, 2024]

    def test_mixed_range_and_single(self):
        assert expand_years("2020:2022", "2025") == [2020, 2021, 2022, 2025]

    def test_single_year_range(self):
        assert expand_years("2023:2023") == [2023]

    def test_returns_ints(self):
        result = expand_years("2020:2021")
        assert all(isinstance(y, int) for y in result)


class TestBuildUrl:
    def test_format(self):
        url = _build_url(2023)
        assert url == "https://portal.inmet.gov.br/uploads/dadoshistoricos/2023.zip"

    def test_different_years(self):
        assert "2000" in _build_url(2000)
        assert "1999" in _build_url(1999)


class TestParseLastModified:
    def test_standard_gmt(self):
        result = _parse_last_modified("Mon, 01 Jan 2024 00:00:00 GMT")
        assert result == dt.datetime(2024, 1, 1, 0, 0, 0)

    def test_different_date(self):
        result = _parse_last_modified("Fri, 15 Mar 2019 12:30:45 GMT")
        assert result == dt.datetime(2019, 3, 15, 12, 30, 45)


class TestBuildFilename:
    def test_format(self):
        lm = dt.datetime(2024, 1, 15)
        assert _build_filename(2023, lm) == "inmet-bdmep_2023_20240115.zip"

    def test_year_in_name(self):
        lm = dt.datetime(2020, 6, 1)
        name = _build_filename(2019, lm)
        assert name.startswith("inmet-bdmep_2019_")
        assert name.endswith(".zip")


class TestRenameCol:
    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("Data", "data"),
            ("Hora UTC", "hora"),
            ("PRECIPITAÇÃO TOTAL, HORÁRIO (mm)", "precipitacao"),
            ("PRESSÃO ATMOSFÉRICA AO NÍVEL DA ESTAÇÃO, HORÁRIA (mB)", "pressao_atmosferica"),
            ("PRESSÃO ATMOSFÉRICA MAX.,NA HORA ANT. (AUT) (mB)", "pressao_atmosferica_maxima"),
            ("PRESSÃO ATMOSFÉRICA MIN., NA HORA ANT. (AUT) (mB)", "pressao_atmosferica_minima"),
            ("RADIAÇÃO GLOBAL (Kj/m²)", "radiacao"),
            ("TEMPERATURA DO AR - BULBO SECO, HORÁRIA (°C)", "temperatura_ar"),
            ("TEMPERATURA DO PONTO DE ORVALHO (°C)", "temperatura_orvalho"),
            ("TEMPERATURA MÁXIMA NA HORA ANT. (AUT) (°C)", "temperatura_maxima"),
            ("TEMPERATURA MÍNIMA NA HORA ANT. (AUT) (°C)", "temperatura_minima"),
            ("TEMPERATURA ORVALHO MAX. NA HORA ANT. (AUT) (°C)", "temperatura_orvalho_maxima"),
            ("TEMPERATURA ORVALHO MIN. NA HORA ANT. (AUT) (°C)", "temperatura_orvalho_minima"),
            ("UMIDADE REL. MAX. NA HORA ANT. (AUT) (%)", "umidade_relativa_maxima"),
            ("UMIDADE REL. MIN. NA HORA ANT. (AUT) (%)", "umidade_relativa_minima"),
            ("UMIDADE RELATIVA DO AR, HORÁRIA (%)", "umidade_relativa"),
            ("VENTO, DIREÇÃO HORÁRIA (gr) (° (gr))", "vento_direcao"),
            ("VENTO, RAJADA MÁXIMA (m/s)", "vento_rajada"),
            ("VENTO, VELOCIDADE HORÁRIA (m/s)", "vento_velocidade"),
        ],
    )
    def test_known_columns(self, raw, expected):
        assert _rename_col(raw) == expected

    def test_unmapped_returns_original(self):
        assert _rename_col("COLUNA_DESCONHECIDA") == "coluna_desconhecida"

    def test_case_insensitive(self):
        assert _rename_col("data") == "data"
        assert _rename_col("DATA") == "data"
        assert _rename_col("Data") == "data"


class TestParseFloat:
    def test_integer_string(self):
        assert _parse_float("42") == 42.0

    def test_dot_decimal(self):
        assert _parse_float("3.14") == pytest.approx(3.14)

    def test_comma_decimal(self):
        assert _parse_float("3,14") == pytest.approx(3.14)

    def test_negative(self):
        assert _parse_float("-3,103") == pytest.approx(-3.103)

    def test_invalid_string_returns_nan(self):
        assert np.isnan(_parse_float(""))

    def test_none_returns_nan(self):
        assert np.isnan(_parse_float(None))

    def test_non_numeric_returns_nan(self):
        assert np.isnan(_parse_float("abc"))


class TestFixHora:
    def test_already_formatted(self):
        assert _fix_hora("00:00") == "00:00"
        assert _fix_hora("23:59") == "23:59"

    def test_utc_format(self):
        assert _fix_hora("0000 UTC") == "00:00"
        assert _fix_hora("1200 UTC") == "12:00"
        assert _fix_hora("2300 UTC") == "23:00"

    def test_four_digit_no_separator(self):
        assert _fix_hora("0600") == "06:00"
