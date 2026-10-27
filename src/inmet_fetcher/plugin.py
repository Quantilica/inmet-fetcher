"""Typer plugin for quantilica-cli integration."""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any

from quantilica.cli.sdk import FetcherApp

from .catalog import GROUP_ALIASES, GROUPS, list_datasets
from .storage import DataRepository


def path_builder(
    output_dir: Path, entry: dict[str, Any], last_modified: dt.date | None
) -> Path:
    """Build the local file path for a downloaded dataset entry.

    Args:
        output_dir: Base directory where data is stored.
        entry: Dataset entry dictionary containing metadata like year and ext.
        last_modified: Optional last modified date to include in the filename.

    Returns:
        Path to the local file for the dataset.
    """
    return DataRepository(output_dir).path_for_entry(entry, last_modified=last_modified)


fetcher = FetcherApp(
    name="inmet-fetcher",
    help="Dados meteorológicos do INMET-BDMEP.",
    groups_dict=GROUPS,
    aliases_dict=GROUP_ALIASES,
    list_datasets=list_datasets,
    path_builder=path_builder,
)


def convert(
    input_dir: Path,
    lake_dir: Path,
    *,
    dataset: list[str] | None = None,
    force: bool = False,
) -> Any:
    """Converte arquivos brutos do INMET para o lake Hive (Parquet)."""
    from inmet_fetcher import lake

    return lake.converter.convert(input_dir, lake_dir, datasets=dataset, force=force)


fetcher.command_convert(convert)
fetcher.command_pipeline(convert)

app = fetcher.app
