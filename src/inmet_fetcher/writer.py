"""Parquet writer for INMET BDMEP observations."""

from __future__ import annotations

from pathlib import Path

import polars as pl
from quantilica.analytics.writer import to_parquet
from quantilica.core.manifests import DownloadManifest

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
