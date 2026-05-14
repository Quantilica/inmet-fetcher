"""Parquet writer for INMET BDMEP observations.

Bridges the pandas-based ``read()`` output to quantilica-io's
standardized Parquet output with manifest-backed provenance.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import polars as pl
from quantilica_core.manifests import DownloadManifest
from quantilica_io.writer import to_parquet

from .schema import BDMEP_CONTRACT


def write_to_parquet(
    df: pd.DataFrame,
    output_path: str | Path,
    *,
    manifest: DownloadManifest | None = None,
    compression: str = "zstd",
) -> Path:
    """Write an INMET BDMEP DataFrame to Parquet.

    Accepts the pandas DataFrame returned by ``read()``/``read_zipfile()``,
    converts to Polars, casts to ``BDMEP_CONTRACT``, and writes with
    manifest provenance in the Parquet header.
    """
    pl_df = pl.from_pandas(df) if not isinstance(df, pl.DataFrame) else df
    casted = BDMEP_CONTRACT.cast(pl_df)
    return to_parquet(
        casted,
        Path(output_path),
        manifest=manifest,
        compression=compression,
    )
