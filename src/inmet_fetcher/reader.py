"""Reading and parsing logic for INMET BDMEP data."""

from __future__ import annotations

import csv
import datetime as dt
import io
import re
import zipfile
from pathlib import Path

import polars as pl
from quantilica.analytics.reader import read_brazilian_csv
from tqdm import tqdm

from .storage import InmetRepository

_COL_PATTERNS = [
    (r"data", "data"),
    (r"hora", "hora"),
    (r"precipita[çc][ãa]o", "precipitacao"),
    (r"press[ãa]o atmosf[ée]rica ao n[íi]vel", "pressao_atmosferica"),
    (r"press[ãa]o atmosf[ée]rica m[áa]x", "pressao_atmosferica_maxima"),
    (r"press[ãa]o atmosf[ée]rica m[íi]n", "pressao_atmosferica_minima"),
    (r"radia[çc][ãa]o", "radiacao"),
    (r"temperatura do ar", "temperatura_ar"),
    (r"temperatura do ponto de orvalho", "temperatura_orvalho"),
    (r"temperatura m[áa]x", "temperatura_maxima"),
    (r"temperatura m[íi]n", "temperatura_minima"),
    (r"temperatura orvalho m[áa]x", "temperatura_orvalho_maxima"),
    (r"temperatura orvalho m[íi]n", "temperatura_orvalho_minima"),
    (r"umidade rel\. m[áa]x", "umidade_relativa_maxima"),
    (r"umidade rel\. m[íi]n", "umidade_relativa_minima"),
    (r"umidade relativa do ar", "umidade_relativa"),
    (r"vento, dire[çc][ãa]o", "vento_direcao"),
    (r"vento, rajada", "vento_rajada"),
    (r"vento, velocidade", "vento_velocidade"),
]

_MEASURE_COLS = [
    "precipitacao",
    "pressao_atmosferica",
    "pressao_atmosferica_maxima",
    "pressao_atmosferica_minima",
    "radiacao",
    "temperatura_ar",
    "temperatura_orvalho",
    "temperatura_maxima",
    "temperatura_minima",
    "temperatura_orvalho_maxima",
    "temperatura_orvalho_minima",
    "umidade_relativa_maxima",
    "umidade_relativa_minima",
    "umidade_relativa",
    "vento_direcao",
    "vento_rajada",
    "vento_velocidade",
]

_META_DTYPES: dict[str, type[pl.DataType]] = {
    "regiao": pl.Utf8,
    "uf": pl.Utf8,
    "estacao": pl.Utf8,
    "codigo_wmo": pl.Utf8,
    "latitude": pl.Float64,
    "longitude": pl.Float64,
    "altitude": pl.Float64,
    "data_fundacao": pl.Datetime,
}


def _rename_col(name: str) -> str:
    name = name.lower()
    for pattern, replacement in _COL_PATTERNS:
        if re.match(pattern, name):
            return replacement
    return name


def _fix_hora(h: str) -> str:
    return h if re.match(r"^\d{2}:\d{2}$", h) else h[:2] + ":00"


def _parse_float(s: str) -> float | None:
    try:
        return float(s.replace(",", "."))
    except (ValueError, AttributeError):
        return None


def read_metadata(f) -> dict:
    if isinstance(f, zipfile.ZipExtFile):
        wrapper = io.TextIOWrapper(f, encoding="latin-1")
    else:
        wrapper = open(f, encoding="latin-1")
    reader = csv.reader(wrapper, delimiter=";")
    _, regiao = next(reader)
    _, uf = next(reader)
    _, estacao = next(reader)
    _, codigo_wmo = next(reader)
    _, lat = next(reader)
    _, lon = next(reader)
    _, alt = next(reader)
    _, data_fundacao = next(reader)
    if re.match(r"\d{4}-\d{2}-\d{2}", data_fundacao):
        data_fundacao = dt.datetime.strptime(data_fundacao, "%Y-%m-%d")
    elif re.match(r"\d{2}/\d{2}/\d{2}", data_fundacao):
        data_fundacao = dt.datetime.strptime(data_fundacao, "%d/%m/%y")
    else:
        data_fundacao = None
    return {
        "regiao": regiao,
        "uf": uf,
        "estacao": estacao,
        "codigo_wmo": codigo_wmo,
        "latitude": _parse_float(lat),
        "longitude": _parse_float(lon),
        "altitude": _parse_float(alt),
        "data_fundacao": data_fundacao,
    }


def read_station_data(f) -> pl.DataFrame:
    d = read_brazilian_csv(
        f,
        engine="polars",
        na_values=["-9999"],
        skip_rows=8,
        truncate_ragged_lines=True,
    )
    # INMET CSVs end each line with ';', creating an extra empty column
    d = d.select(d.columns[:19])
    d = d.rename({col: _rename_col(col) for col in d.columns})
    # Remove rows where every measurement column is null
    measure_cols = [c for c in _MEASURE_COLS if c in d.columns]
    d = d.filter(pl.any_horizontal(pl.col(c).is_not_null() for c in measure_cols))
    # Parse datetime: "0000 UTC" → "00:00", already "HH:MM" stays unchanged
    d = d.with_columns(
        pl.concat_str(
            [
                pl.col("data").str.replace_all("/", "-"),
                pl.when(pl.col("hora").str.contains(r"^\d{2}:\d{2}$"))
                .then(pl.col("hora"))
                .otherwise(pl.col("hora").str.slice(0, 2) + ":00"),
            ],
            separator=" ",
        )
        .str.to_datetime("%Y-%m-%d %H:%M")
        .alias("data_hora")
    )
    return d.drop(["data", "hora"])


def read_zipfile(
    filepath: Path,
    *,
    uf: list[str] | None = None,
    station: list[str] | None = None,
    start: str | None = None,
    end: str | None = None,
) -> pl.DataFrame:
    frames = []
    with zipfile.ZipFile(filepath) as z:
        files = [zf for zf in z.infolist() if not zf.is_dir()]
        for zf in tqdm(files, desc=filepath.name, leave=False, dynamic_ncols=True):
            meta = read_metadata(z.open(zf.filename))
            if uf and meta["uf"] not in uf:
                continue
            if station and meta["codigo_wmo"] not in station:
                continue
            d = read_station_data(z.open(zf.filename))
            d = d.with_columns(
                [pl.lit(meta[k], dtype=_META_DTYPES[k]).alias(k) for k in _META_DTYPES]
            )
            frames.append(d)
    if not frames:
        return pl.DataFrame()
    data = pl.concat(frames)
    if start:
        data = data.filter(pl.col("data_hora") >= dt.datetime.fromisoformat(start))
    if end:
        data = data.filter(pl.col("data_hora") <= dt.datetime.fromisoformat(end))
    return data


def find_zipfiles(data_dir: Path, years: list[int] | None = None) -> list[Path]:
    """Locate INMET BDMEP ZIPs under ``bdmep/{year}/*.zip`` (Padrão B)."""
    repo = InmetRepository(data_dir)
    zips: list[Path] = []
    if years:
        for year in years:
            year_dir = repo.dataset_path("bdmep", str(year))
            if year_dir.exists():
                zips.extend(sorted(year_dir.glob("*.zip")))
    else:
        bdmep_root = repo.dataset_path("bdmep")
        if bdmep_root.exists():
            zips.extend(sorted(bdmep_root.rglob("*.zip")))

    return sorted(set(zips))


def read(
    data_dir: Path,
    years: list[int] | None = None,
    uf: list[str] | None = None,
    station: list[str] | None = None,
    start: str | None = None,
    end: str | None = None,
) -> pl.DataFrame:
    zips = find_zipfiles(data_dir, years)
    if not zips:
        raise FileNotFoundError(f"Nenhum ZIP encontrado em {data_dir}")
    frames = [
        read_zipfile(z, uf=uf, station=station, start=start, end=end)
        for z in tqdm(zips, desc="lendo ZIPs", dynamic_ncols=True)
    ]
    if not frames:
        return pl.DataFrame()
    return pl.concat(frames)


def read_stations(data_dir: Path, years: list[int] | None = None) -> pl.DataFrame:
    zips = find_zipfiles(data_dir, years)
    if not zips:
        raise FileNotFoundError(f"Nenhum ZIP encontrado em {data_dir}")
    records = []
    for filepath in tqdm(zips, desc="lendo ZIPs", dynamic_ncols=True):
        with zipfile.ZipFile(filepath) as z:
            for zf in z.infolist():
                if not zf.is_dir():
                    records.append(read_metadata(z.open(zf.filename)))
    if not records:
        return pl.DataFrame()
    df = pl.DataFrame({k: [r[k] for r in records] for k in records[0]})
    return df.unique(subset=["codigo_wmo"]).sort("codigo_wmo")
