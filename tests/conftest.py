import io
import zipfile
from pathlib import Path

import pytest

# 8 metadata rows + header row + data — matches INMET CSV format
_META_LINES = (
    "REGIAO:;{regiao}",
    "UF:;{uf}",
    "ESTACAO:;{estacao}",
    "CODIGO (WMO):;{codigo_wmo}",
    "LATITUDE:;{latitude}",
    "LONGITUDE:;{longitude}",
    "ALTITUDE:;{altitude}",
    "DATA DE FUNDACAO:;{data_fundacao}",
)

# 19 columns + trailing ; (usecols=range(19) takes first 19, ignores 20th empty)
CSV_HEADER = (
    "Data;Hora UTC;"
    "PRECIPITAÇÃO TOTAL, HORÁRIO (mm);"
    "PRESSÃO ATMOSFÉRICA AO NÍVEL DA ESTAÇÃO, HORÁRIA (mB);"
    "PRESSÃO ATMOSFÉRICA MAX.,NA HORA ANT. (AUT) (mB);"
    "PRESSÃO ATMOSFÉRICA MIN., NA HORA ANT. (AUT) (mB);"
    "RADIAÇÃO GLOBAL (Kj/m²);"
    "TEMPERATURA DO AR - BULBO SECO, HORÁRIA (°C);"
    "TEMPERATURA DO PONTO DE ORVALHO (°C);"
    "TEMPERATURA MÁXIMA NA HORA ANT. (AUT) (°C);"
    "TEMPERATURA MÍNIMA NA HORA ANT. (AUT) (°C);"
    "TEMPERATURA ORVALHO MAX. NA HORA ANT. (AUT) (°C);"
    "TEMPERATURA ORVALHO MIN. NA HORA ANT. (AUT) (°C);"
    "UMIDADE REL. MAX. NA HORA ANT. (AUT) (%);"
    "UMIDADE REL. MIN. NA HORA ANT. (AUT) (%);"
    "UMIDADE RELATIVA DO AR, HORÁRIA (%);"
    "VENTO, DIREÇÃO HORÁRIA (gr) (° (gr));"
    "VENTO, RAJADA MÁXIMA (m/s);"
    "VENTO, VELOCIDADE HORÁRIA (m/s);"
)

DEFAULT_DATA_ROWS = [
    "2023-01-01;0000 UTC;0,0;1013,2;1013,5;1012,8;100,0;28,5;24,0;29,0;28,0;25,0;23,5;85;80;82;180;5,2;3,1;",
    "2023-01-01;0100 UTC;0,2;1012,8;1013,2;1012,5;0,0;27,8;23,5;28,5;27,5;24,5;23,0;87;82;85;190;4,8;2,9;",
    "2023-01-02;0000 UTC;1,4;1011,0;1012,0;1010,5;120,0;30,1;25,5;31,0;29,5;26,0;24,5;80;75;78;200;6,0;3,5;",
]

ALL_NULL_ROW = (
    "2023-01-03;0000 UTC;"
    "-9999;-9999;-9999;-9999;-9999;-9999;-9999;-9999;-9999;"
    "-9999;-9999;-9999;-9999;-9999;-9999;-9999;-9999;"
)


def make_station_csv(
    regiao="Norte",
    uf="AM",
    estacao="Estação Teste",
    codigo_wmo="A001",
    latitude="-3,103",
    longitude="-60,016",
    altitude="48,0",
    data_fundacao="1990-01-01",
    data_rows=None,
) -> bytes:
    meta = [
        line.format(
            regiao=regiao,
            uf=uf,
            estacao=estacao,
            codigo_wmo=codigo_wmo,
            latitude=latitude,
            longitude=longitude,
            altitude=altitude,
            data_fundacao=data_fundacao,
        )
        for line in _META_LINES
    ]
    rows = data_rows if data_rows is not None else DEFAULT_DATA_ROWS
    lines = meta + [CSV_HEADER] + rows
    return "\n".join(lines).encode("latin-1")


def make_zip_bytes(*stations: tuple) -> bytes:
    """stations: sequence of (filename, kwargs) tuples"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for filename, kwargs in stations:
            z.writestr(filename, make_station_csv(**kwargs))
    buf.seek(0)
    return buf.read()


@pytest.fixture
def sample_zip_bytes():
    return make_zip_bytes(
        ("INMET_N_AM_A001_EstacaoTeste_01-01-2023_A_01-01-2024.CSV", {}),
    )


@pytest.fixture
def multi_station_zip_bytes():
    return make_zip_bytes(
        (
            "INMET_N_AM_A001_EstacaoAM_01-01-2023_A_01-01-2024.CSV",
            {"uf": "AM", "codigo_wmo": "A001"},
        ),
        (
            "INMET_SE_SP_B001_EstacaoSP_01-01-2023_A_01-01-2024.CSV",
            {"uf": "SP", "codigo_wmo": "B001", "regiao": "Sudeste"},
        ),
        (
            "INMET_SE_RJ_C001_EstacaoRJ_01-01-2023_A_01-01-2024.CSV",
            {"uf": "RJ", "codigo_wmo": "C001", "regiao": "Sudeste"},
        ),
    )


@pytest.fixture
def sample_zip_path(tmp_path, sample_zip_bytes):
    path = tmp_path / "inmet-bdmep_2023_20240101.zip"
    path.write_bytes(sample_zip_bytes)
    return path


@pytest.fixture
def multi_year_data_dir(tmp_path, make_zip):
    for year in [2021, 2022, 2023]:
        path = tmp_path / f"inmet-bdmep_{year}_20240101.zip"
        path.write_bytes(
            make_zip_bytes(
                (f"INMET_N_AM_A001_EstacaoTeste_{year}.CSV", {"codigo_wmo": "A001"}),
            )
        )
    return tmp_path


@pytest.fixture
def make_zip():
    return make_zip_bytes
