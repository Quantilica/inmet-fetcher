"""Parquet writer for INMET BDMEP observations."""

from __future__ import annotations

from pathlib import Path

import polars as pl
from quantilica_core.manifests import DownloadManifest
from quantilica_io.writer import to_parquet

from .schema import BDMEP_CONTRACT


def write_to_parquet(
    df: pl.DataFrame,
    output_path: str | Path,
    *,
    manifest: DownloadManifest | None = None,
    compression: str = "zstd",
) -> Path:
    casted = BDMEP_CONTRACT.cast(df)
    return to_parquet(
        casted,
        Path(output_path),
        manifest=manifest,
        compression=compression,
    )
