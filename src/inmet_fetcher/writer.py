"""Parquet writer for INMET BDMEP observations."""

from __future__ import annotations

from pathlib import Path

try:
    import polars as pl
    from quantilica.analytics.writer import to_parquet
except ImportError as exc:
    raise ImportError(
        "inmet_fetcher.writer requer o extra 'analysis': "
        "uv add 'inmet-fetcher[analysis]' "
        "--index https://index.quantilica.com/simple/"
    ) from exc
from quantilica.core.manifests import DownloadManifest

from .schema import BDMEP_CONTRACT


def write_to_parquet(
    df: pl.DataFrame,
    output_path: str | Path,
    *,
    manifest: DownloadManifest | None = None,
    compression: str = "zstd",
) -> Path:
    """Write DataFrame to Parquet file applying the BDMEP schema contract.

    Args:
        df: The Polars DataFrame to write.
        output_path: The destination path for the Parquet file.
        manifest: Optional download manifest to attach as metadata.
        compression: The compression algorithm to use. Defaults to "zstd".

    Returns:
        The Path to the written Parquet file.
    """
    casted = BDMEP_CONTRACT.cast(df)
    return to_parquet(
        casted,
        Path(output_path),
        manifest=manifest,
        compression=compression,
    )
