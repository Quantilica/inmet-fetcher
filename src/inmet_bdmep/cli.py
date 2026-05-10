"""Command-line interface for INMET BDMEP."""

from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path

from .fetch import expand_years, fetch
from .reader import read, read_stations


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
