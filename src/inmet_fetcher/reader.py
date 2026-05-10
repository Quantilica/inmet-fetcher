"""Reading and parsing logic for INMET BDMEP data."""

from __future__ import annotations

import csv
import datetime as dt
import io
import re
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
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


def _rename_col(name: str) -> str:
    name = name.lower()
    for pattern, replacement in _COL_PATTERNS:
        if re.match(pattern, name):
            return replacement
    return name


def _parse_float(s: str) -> float:
    try:
        return float(s.replace(",", "."))
    except (ValueError, AttributeError):
        return np.nan


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


def _fix_hora(h: str) -> str:
    return h if re.match(r"^\d{2}:\d{2}$", h) else h[:2] + ":00"


def read_station_data(f) -> pd.DataFrame:
    d = pd.read_csv(
        f,
        sep=";",
        decimal=",",
        na_values="-9999",
        encoding="latin-1",
        skiprows=8,
        usecols=range(19),
    )
    d = d.rename(columns=_rename_col)
    d = d.loc[~d[_MEASURE_COLS].isnull().all(axis=1)]
    dates = d["data"].str.replace("/", "-")
    hours = d["hora"].apply(_fix_hora)
    d = d.assign(
        data_hora=pd.to_datetime(dates + " " + hours, format="%Y-%m-%d %H:%M"),
    )
    return d.drop(columns=["data", "hora"])


def read_zipfile(
    filepath: Path,
    *,
    uf: list[str] | None = None,
    station: list[str] | None = None,
    start: str | None = None,
    end: str | None = None,
) -> pd.DataFrame:
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
            d = d.assign(**meta)
            frames.append(d)
    if not frames:
        return pd.DataFrame()
    data = pd.concat(frames, ignore_index=True)
    if start:
        data = data.loc[data["data_hora"] >= pd.Timestamp(start)]
    if end:
        data = data.loc[data["data_hora"] <= pd.Timestamp(end)]
    return data


def find_zipfiles(data_dir: Path, years: list[int] | None = None) -> list[Path]:
    # We now look into the new repository structure if it exists, or the old one for compatibility
    repo = InmetRepository(data_dir)
    zips = []
    if years:
        for year in years:
            # Check new structure
            path = repo.path_for_year(year, f"{year}.zip")
            if path.exists():
                zips.append(path)
            else:
                # Check legacy flat structure
                legacy_zips = sorted(data_dir.glob(f"inmet-bdmep_{year}_*.zip"))
                zips.extend(legacy_zips)
    else:
        # Search everywhere under raw/bdmep
        zips = sorted(data_dir.rglob("raw/bdmep/**/*.zip"))
        # And legacy
        zips.extend(sorted(data_dir.glob("inmet-bdmep_*.zip")))
    
    return sorted(list(set(zips)))


def read(
    data_dir: Path,
    years: list[int] | None = None,
    uf: list[str] | None = None,
    station: list[str] | None = None,
    start: str | None = None,
    end: str | None = None,
    engine: str = "pandas",
) -> pd.DataFrame:
    zips = find_zipfiles(data_dir, years)
    if not zips:
        raise FileNotFoundError(f"Nenhum ZIP encontrado em {data_dir}")
    frames = [
        read_zipfile(z, uf=uf, station=station, start=start, end=end)
        for z in tqdm(zips, desc="lendo ZIPs", dynamic_ncols=True)
    ]
    if not frames:
        return pd.DataFrame()
    data = pd.concat(frames, ignore_index=True)
    if engine == "polars":
        try:
            import polars as pl

            return pl.from_pandas(data)
        except ImportError:
            raise ImportError("polars não instalado. Execute: pip install polars")
    return data


def read_stations(data_dir: Path, years: list[int] | None = None) -> pd.DataFrame:
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
        return pd.DataFrame()
    df = pd.DataFrame(records).drop_duplicates(subset=["codigo_wmo"])
    return df.sort_values("codigo_wmo").reset_index(drop=True)
