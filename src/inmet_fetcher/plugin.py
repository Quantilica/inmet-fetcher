# Copyright (c) 2026 Komesu, D.K.
# Licensed under the MIT License.

"""Typer plugin for quantilica-cli integration."""

from __future__ import annotations

import concurrent.futures
import datetime as dt
from pathlib import Path
from typing import Annotated

import polars as pl
import typer
from quantilica.core.cli import (
    ProgressPool,
    expand_years_cli,
    get_console,
    graceful_executor,
    make_batch_progress,
    make_download_progress,
    setup_rich_logging,
)
from rich.console import Group
from rich.live import Live

from inmet_fetcher.fetch import download_year, fetch
from inmet_fetcher.reader import read, read_stations
from inmet_fetcher.storage import InmetRepository

app = typer.Typer(help="Dados meteorológicos do INMET-BDMEP.")

_DEFAULT_OUTPUT = Path("/data/inmet")
_CURRENT_YEAR = dt.datetime.now().year
console = get_console()


def _save(data: pl.DataFrame, output: Path, fmt: str) -> None:
    if fmt == "parquet":
        data.write_parquet(output)
    elif fmt == "csv":
        data.write_csv(output)
    elif fmt == "json":
        data.write_json(output)
    console.print(
        f"[green]✓[/green] Salvo em [bold]{output}[/bold] ({len(data):,} linhas)"
    )


@app.command("sync")
def cmd_sync(
    years: Annotated[
        list[str] | None,
        typer.Argument(
            help="Anos (ex: 2020 2021 ou 2020:2024). Padrão: todos os anos."
        ),
    ] = None,
    output: Annotated[
        Path, typer.Option("-o", "--output", help="Diretório de destino")
    ] = _DEFAULT_OUTPUT,
    workers: Annotated[int, typer.Option("--workers", help="Downloads paralelos")] = 4,
    verbose: Annotated[bool, typer.Option("--verbose", help="Logs detalhados")] = False,
) -> None:
    """Sincronizar dados do INMET."""
    setup_rich_logging(verbose, console=console)
    expanded = expand_years_cli(
        years, default_range=f"2000:{_CURRENT_YEAR}", console=console
    )
    total = len(expanded)

    if total == 0:
        console.print("[yellow]Nenhum ano selecionado para sincronizar.[/yellow]")
        return

    if verbose:
        paths = fetch(expanded, output, workers=workers)
        n = len(paths)
        if n:
            console.print(
                f"[green]✓[/green] [bold]{n}[/bold] arquivo(s) sincronizado(s)."
            )
        else:
            console.print("[yellow]Nenhum arquivo novo para sincronizar.[/yellow]")
        return

    repo = InmetRepository(output)
    overall = make_batch_progress(console)
    file_prog = make_download_progress(console)
    overall_task = overall.add_task("[cyan]Baixando...[/cyan]", total=total)

    downloaded = 0
    errors: list[tuple[str, str]] = []

    pool = ProgressPool(workers=workers, file_prog=file_prog)

    def _worker(year: int) -> bool:
        try:
            with pool.acquire(description=f"[cyan]{year}[/cyan]") as cb:
                path = download_year(year, repo, progress=cb)
                return path is not None
        except Exception as exc:
            errors.append((str(year), str(exc)))
            return False

    with graceful_executor(max_workers=workers) as executor:
        try:
            with Live(
                Group(overall, file_prog), console=console, refresh_per_second=10
            ):
                futures = {executor.submit(_worker, y): y for y in expanded}
                for future in concurrent.futures.as_completed(futures):
                    overall.update(overall_task, advance=1)
                    if future.result():
                        downloaded += 1
        except KeyboardInterrupt:
            console.print("\n[yellow]Interrompido.[/yellow]")
            raise typer.Exit(130) from None

    if downloaded:
        console.print(
            f"[green]✓[/green] [bold]{downloaded}[/bold] arquivo(s) sincronizado(s)."
        )
    else:
        console.print("[yellow]Nenhum arquivo novo para sincronizar.[/yellow]")

    if errors:
        console.print(f"[red]{len(errors)} erro(s):[/red]")
        for eid, emsg in errors:
            console.print(f"  {eid}: {emsg}")


@app.command("read")
def cmd_read(
    output: Annotated[
        Path, typer.Option("-o", "--output", help="Diretório de dados")
    ] = _DEFAULT_OUTPUT,
    years: Annotated[
        list[str] | None,
        typer.Option("--years", help="Filtrar anos (ex: 2020 ou 2020:2024)"),
    ] = None,
    uf: Annotated[
        str | None,
        typer.Option("--uf", help="UFs separadas por vírgula (ex: SP,RJ,MG)"),
    ] = None,
    station: Annotated[
        str | None, typer.Option("--station", help="Códigos WMO separados por vírgula")
    ] = None,
    start: Annotated[
        str | None, typer.Option("--start", help="Data início (ex: 2020-01-01)")
    ] = None,
    end: Annotated[
        str | None, typer.Option("--end", help="Data fim (ex: 2020-12-31)")
    ] = None,
    save_as: Annotated[
        Path | None, typer.Option("--save-as", help="Arquivo de exportação")
    ] = None,
    fmt: Annotated[str, typer.Option("--format", help="Formato de saída")] = "parquet",
    verbose: Annotated[bool, typer.Option("--verbose", help="Logs detalhados")] = False,
) -> None:
    """Ler e exportar dados do INMET."""
    setup_rich_logging(verbose, console=console)
    uf_list = [u.strip().upper() for u in uf.split(",")] if uf else None
    station_list = [s.strip() for s in station.split(",")] if station else None
    years_list = expand_years_cli(years, console=console) if years else None
    data = read(
        output, years=years_list, uf=uf_list, station=station_list, start=start, end=end
    )
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
        list[str] | None, typer.Option("--years", help="Filtrar anos para metadados")
    ] = None,
    save_as: Annotated[
        Path | None, typer.Option("--save-as", help="Arquivo de exportação")
    ] = None,
    fmt: Annotated[str, typer.Option("--format", help="Formato de saída")] = "csv",
    verbose: Annotated[bool, typer.Option("--verbose", help="Logs detalhados")] = False,
) -> None:
    """Exportar catálogo de estações meteorológicas."""
    setup_rich_logging(verbose, console=console)
    years_list = expand_years_cli(years, console=console) if years else None
    data = read_stations(output, years=years_list)
    if len(data) == 0:
        console.print("[yellow]Nenhuma estação encontrada.[/yellow]")
        return
    if save_as:
        _save(data, save_as, fmt)
    else:
        console.print(str(data))
