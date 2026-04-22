import argparse
import concurrent.futures
import csv
import datetime as dt
import io
import re
import zipfile
from pathlib import Path

import httpx
import numpy as np
import pandas as pd
from tqdm import tqdm

# ─── FETCH ──────────────────────────────────────────────────────────────────


def expand_years(*years: str) -> list[int]:
    year_list = []
    for y in years:
        if ":" in y:
            start, end = y.split(":")
            year_list.extend(range(int(start), int(end) + 1))
        else:
            year_list.append(int(y))
    return year_list


def _build_url(year: int) -> str:
    return f"https://portal.inmet.gov.br/uploads/dadoshistoricos/{year}.zip"


def _parse_last_modified(value: str) -> dt.datetime:
    return dt.datetime.strptime(value, "%a, %d %b %Y %H:%M:%S %Z")


def _build_filename(year: int, last_modified: dt.datetime) -> str:
    return f"inmet-bdmep_{year}_{last_modified:%Y%m%d}.zip"


def download_year(year: int, destdir: Path, position: int = 0) -> Path | None:
    destdir.mkdir(parents=True, exist_ok=True)
    url = _build_url(year)
    with httpx.Client(headers={"User-Agent": "Mozilla/5.0"}) as client:
        try:
            headers = client.head(url, timeout=10).headers
        except httpx.HTTPError:
            tqdm.write(f"Erro ao acessar {url}")
            return None
        if "Last-Modified" not in headers:
            tqdm.write(f"Arquivo não encontrado: {year}")
            return None
        last_modified = _parse_last_modified(headers["Last-Modified"])
        file_size = int(headers.get("Content-Length", 0))
        destpath = destdir / _build_filename(year, last_modified)
        if destpath.exists() and destpath.stat().st_size == file_size:
            tqdm.write(f"{year}: já existe, pulando")
            return destpath
        pb = tqdm(
            desc=str(year),
            total=file_size,
            unit="iB",
            unit_scale=True,
            dynamic_ncols=True,
            position=position,
            leave=True,
        )
        with client.stream("GET", url, timeout=None) as r:
            with open(destpath, "wb") as f:
                for chunk in r.iter_bytes(2048):
                    f.write(chunk)
                    pb.update(len(chunk))
        pb.close()
        return destpath


def fetch(years: list[int], destdir: Path, workers: int = 4) -> list[Path]:
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_year = {
            executor.submit(download_year, year, destdir, i % workers): year
            for i, year in enumerate(years)
        }
        for future in concurrent.futures.as_completed(future_to_year):
            path = future.result()
            if path:
                results.append(path)
    return sorted(results)


# ─── READ ───────────────────────────────────────────────────────────────────

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
    zips = sorted(data_dir.glob("inmet-bdmep_*.zip"))
    if years:
        year_strs = {str(y) for y in years}
        zips = [z for z in zips if z.name.split("_")[1] in year_strs]
    return zips


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


# ─── CLI ────────────────────────────────────────────────────────────────────


def _save(data, output: Path, fmt: str) -> None:
    try:
        import polars as pl

        is_polars = isinstance(data, pl.DataFrame)
    except ImportError:
        is_polars = False

    if is_polars:
        if fmt == "parquet":
            data.write_parquet(output)
        elif fmt == "csv":
            data.write_csv(output)
        elif fmt == "json":
            data.write_json(output)
    else:
        if fmt == "parquet":
            data.to_parquet(output, index=False)
        elif fmt == "csv":
            data.to_csv(output, index=False)
        elif fmt == "json":
            data.to_json(output, orient="records", date_format="iso")
    print(f"Salvo: {output} ({len(data):,} linhas)")


def _cmd_fetch(args):
    years = expand_years(*args.years)
    fetch(years, args.data_dir, workers=args.workers)


def _cmd_read(args):
    uf = [u.strip().upper() for u in args.uf.split(",")] if args.uf else None
    station = [s.strip() for s in args.station.split(",")] if args.station else None
    years = expand_years(*args.years) if args.years else None
    data = read(
        args.data_dir,
        years=years,
        uf=uf,
        station=station,
        start=args.start,
        end=args.end,
        engine=args.engine,
    )
    if len(data) == 0:
        print("Nenhum dado encontrado.")
        return
    if args.output:
        _save(data, args.output, args.format)
    else:
        print(data)


def _cmd_stations(args):
    years = expand_years(*args.years) if args.years else None
    data = read_stations(args.data_dir, years=years)
    if len(data) == 0:
        print("Nenhuma estação encontrada.")
        return
    if args.output:
        _save(data, args.output, args.format)
    else:
        print(data.to_string())


def main_cli():
    current_year = dt.datetime.now().year
    parser = argparse.ArgumentParser(
        prog="inmet",
        description="INMET BDMEP — coleta e leitura de dados meteorológicos",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    # fetch
    p_fetch = sub.add_parser("fetch", help="Baixar dados do INMET")
    p_fetch.add_argument(
        "years",
        nargs="+",
        default=[f"2000:{current_year}"],
        help="Anos (ex: 2020 2021 ou 2020:2024)",
    )
    p_fetch.add_argument(
        "--data-dir",
        dest="data_dir",
        type=Path,
        required=True,
        help="Diretório de destino",
    )
    p_fetch.add_argument(
        "--workers", type=int, default=4, help="Downloads paralelos (padrão: 4)"
    )

    # read
    p_read = sub.add_parser("read", help="Ler e exportar dados")
    p_read.add_argument("--data-dir", dest="data_dir", type=Path, required=True)
    p_read.add_argument(
        "--years", nargs="+", default=None, help="Filtrar anos (ex: 2020 ou 2020:2024)"
    )
    p_read.add_argument(
        "--uf", default=None, help="Filtrar UFs separadas por vírgula (ex: SP,RJ,MG)"
    )
    p_read.add_argument(
        "--station",
        default=None,
        help="Filtrar estações por código WMO (ex: A001,A002)",
    )
    p_read.add_argument("--start", default=None, help="Data início (ex: 2020-01-01)")
    p_read.add_argument("--end", default=None, help="Data fim (ex: 2020-12-31)")
    p_read.add_argument("--output", type=Path, default=None, help="Arquivo de saída")
    p_read.add_argument(
        "--format",
        choices=["parquet", "csv", "json"],
        default="parquet",
        help="Formato de saída (padrão: parquet)",
    )
    p_read.add_argument(
        "--engine",
        choices=["pandas", "polars"],
        default="pandas",
        help="Engine de processamento (padrão: pandas)",
    )

    # stations
    p_sta = sub.add_parser("stations", help="Exportar catálogo de estações")
    p_sta.add_argument("--data-dir", dest="data_dir", type=Path, required=True)
    p_sta.add_argument(
        "--years",
        nargs="+",
        default=None,
        help="Filtrar anos para extração de metadados",
    )
    p_sta.add_argument("--output", type=Path, default=None, help="Arquivo de saída")
    p_sta.add_argument(
        "--format",
        choices=["parquet", "csv", "json"],
        default="csv",
        help="Formato de saída (padrão: csv)",
    )

    args = parser.parse_args()
    {"fetch": _cmd_fetch, "read": _cmd_read, "stations": _cmd_stations}[args.cmd](args)


if __name__ == "__main__":
    main_cli()
