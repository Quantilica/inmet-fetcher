"""Command-line interface for INMET BDMEP."""

from __future__ import annotations

import argparse
import datetime as dt
import logging
from pathlib import Path

from quantilica_core.logging import configure_cli_logging

from . import __version__
from .fetch import expand_years, fetch, logger
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


def _cmd_sync(args):
    years = expand_years(*args.years) if args.years else expand_years(f"2000:{dt.datetime.now().year}")
    fetch(years, args.output, workers=args.workers, show_progress=not args.verbose)


def _cmd_read(args):
    uf = [u.strip().upper() for u in args.uf.split(",")] if args.uf else None
    station = [s.strip() for s in args.station.split(",")] if args.station else None
    years = expand_years(*args.years) if args.years else None
    data = read(
        args.output,
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
    if args.save_as:
        _save(data, args.save_as, args.format)
    else:
        print(data)


def _cmd_stations(args):
    years = expand_years(*args.years) if args.years else None
    data = read_stations(args.output, years=years)
    if len(data) == 0:
        print("Nenhuma estação encontrada.")
        return
    if args.save_as:
        _save(data, args.save_as, args.format)
    else:
        print(data.to_string())


def main_cli():
    current_year = dt.datetime.now().year
    parser = argparse.ArgumentParser(
        prog="inmet",
        description="INMET BDMEP — coleta e leitura de dados meteorológicos",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        default=False,
        help="Exibir logs detalhados em vez de barra de progresso",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    # sync
    p_sync = sub.add_parser("sync", help="Sincronizar dados do INMET")
    p_sync.add_argument(
        "years",
        nargs="*",
        default=None,
        help="Anos (ex: 2020 2021 ou 2020:2024). Padrão: todos os anos.",
    )
    p_sync.add_argument(
        "-o",
        "--output",
        dest="output",
        type=Path,
        default=Path("/data/inmet"),
        help="Diretório de destino (padrão: /data/inmet)",
    )
    p_sync.add_argument(
        "--workers", type=int, default=4, help="Downloads paralelos (padrão: 4)"
    )

    # read
    p_read = sub.add_parser("read", help="Ler e exportar dados")
    p_read.add_argument(
        "-o",
        "--output",
        dest="output",
        type=Path,
        default=Path("/data/inmet"),
        help="Diretório de dados (padrão: /data/inmet)",
    )
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
    p_read.add_argument(
        "--save-as",
        dest="save_as",
        type=Path,
        default=None,
        help="Arquivo de exportação (se omitido, imprime no stdout)",
    )
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
    p_sta.add_argument(
        "-o",
        "--output",
        dest="output",
        type=Path,
        default=Path("/data/inmet"),
        help="Diretório de dados (padrão: /data/inmet)",
    )
    p_sta.add_argument(
        "--years",
        nargs="+",
        default=None,
        help="Filtrar anos para extração de metadados",
    )
    p_sta.add_argument(
        "--save-as",
        dest="save_as",
        type=Path,
        default=None,
        help="Arquivo de exportação (se omitido, imprime no stdout)",
    )
    p_sta.add_argument(
        "--format",
        choices=["parquet", "csv", "json"],
        default="csv",
        help="Formato de saída (padrão: csv)",
    )

    args = parser.parse_args()
    configure_cli_logging(verbose=args.verbose)
    if not args.verbose:
        logging.getLogger("inmet_fetcher").setLevel(logging.WARNING)
    {"sync": _cmd_sync, "read": _cmd_read, "stations": _cmd_stations}[args.cmd](args)
