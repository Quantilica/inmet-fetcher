# Copyright (c) 2026 Komesu, D.K.
# Licensed under the MIT License.

"""Typer plugin for quantilica-cli integration."""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console

from inmet_fetcher.fetch import expand_years, fetch
from inmet_fetcher.reader import read, read_stations

app = typer.Typer(help="Dados meteorológicos do INMET-BDMEP.")

_DEFAULT_OUTPUT = Path("/data/inmet")
_CURRENT_YEAR = dt.datetime.now().year
console = Console()


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
    console.print(f"[green]✓[/green] Salvo em [bold]{output}[/bold] ({len(data):,} linhas)")


@app.command("fetch")
def cmd_fetch(
    years: Annotated[
        list[str],
        typer.Argument(help="Anos (ex: 2020 2021 ou 2020:2024)"),
    ] = [f"2000:{_CURRENT_YEAR}"],
    output: Annotated[
        Path, typer.Option("-o", "--output", help="Diretório de destino")
    ] = _DEFAULT_OUTPUT,
    workers: Annotated[
        int, typer.Option("--workers", help="Downloads paralelos")
    ] = 4,
) -> None:
    """Baixar dados do INMET."""
    with console.status("[cyan]Baixando dados do INMET...[/cyan]"):
        fetch(expand_years(*years), output, workers=workers)


@app.command("read")
def cmd_read(
    output: Annotated[
        Path, typer.Option("-o", "--output", help="Diretório de dados")
    ] = _DEFAULT_OUTPUT,
    years: Annotated[
        Optional[list[str]], typer.Option("--years", help="Filtrar anos (ex: 2020 ou 2020:2024)")
    ] = None,
    uf: Annotated[
        Optional[str], typer.Option("--uf", help="UFs separadas por vírgula (ex: SP,RJ,MG)")
    ] = None,
    station: Annotated[
        Optional[str], typer.Option("--station", help="Códigos WMO separados por vírgula")
    ] = None,
    start: Annotated[
        Optional[str], typer.Option("--start", help="Data início (ex: 2020-01-01)")
    ] = None,
    end: Annotated[
        Optional[str], typer.Option("--end", help="Data fim (ex: 2020-12-31)")
    ] = None,
    save_as: Annotated[
        Optional[Path], typer.Option("--save-as", help="Arquivo de exportação")
    ] = None,
    fmt: Annotated[
        str, typer.Option("--format", help="Formato de saída")
    ] = "parquet",
    engine: Annotated[
        str, typer.Option("--engine", help="Engine de processamento (pandas|polars)")
    ] = "pandas",
) -> None:
    """Ler e exportar dados do INMET."""
    uf_list = [u.strip().upper() for u in uf.split(",")] if uf else None
    station_list = [s.strip() for s in station.split(",")] if station else None
    years_list = expand_years(*years) if years else None
    data = read(output, years=years_list, uf=uf_list, station=station_list, start=start, end=end, engine=engine)
    if len(data) == 0:
        console.print("[yellow]Nenhum dado encontrado.[/yellow]")
        return
    if save_as:
        _save(data, save_as, fmt)
    else:
        console.print(str(data))


@app.command("stations")
def cmd_stations(
    output: Annotated[
        Path, typer.Option("-o", "--output", help="Diretório de dados")
    ] = _DEFAULT_OUTPUT,
    years: Annotated[
        Optional[list[str]], typer.Option("--years", help="Filtrar anos para metadados")
    ] = None,
    save_as: Annotated[
        Optional[Path], typer.Option("--save-as", help="Arquivo de exportação")
    ] = None,
    fmt: Annotated[
        str, typer.Option("--format", help="Formato de saída")
    ] = "csv",
) -> None:
    """Exportar catálogo de estações meteorológicas."""
    years_list = expand_years(*years) if years else None
    data = read_stations(output, years=years_list)
    if len(data) == 0:
        console.print("[yellow]Nenhuma estação encontrada.[/yellow]")
        return
    if save_as:
        _save(data, save_as, fmt)
    else:
        console.print(data.to_string())
