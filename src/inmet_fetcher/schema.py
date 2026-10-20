"""Data contract for INMET BDMEP observations.

Captures the long-format schema produced by ``read()``: 17 measurement
columns (from ``_MEASURE_COLS``), station metadata fields, and the
``data_hora`` timestamp.
"""

from __future__ import annotations

try:
    import polars as pl
    from quantilica.analytics.schema import DataContract, Field
except ImportError as exc:
    raise ImportError(
        "inmet_fetcher.schema requer o extra 'analysis': "
        "uv add 'inmet-fetcher[analysis]' "
        "--index https://index.quantilica.com/simple/"
    ) from exc

from .reader import _MEASURE_COLS

_METADATA_FIELDS: list[Field] = [
    Field(name="regiao", dtype=pl.Utf8),
    Field(name="uf", dtype=pl.Utf8),
    Field(name="estacao", dtype=pl.Utf8),
    Field(name="codigo_wmo", dtype=pl.Utf8),
    Field(name="latitude", dtype=pl.Float64, required=False),
    Field(name="longitude", dtype=pl.Float64, required=False),
    Field(name="altitude", dtype=pl.Float64, required=False),
    Field(name="data_fundacao", dtype=pl.Datetime, required=False),
    Field(name="data_hora", dtype=pl.Datetime(time_zone="UTC")),
]

_MEASURE_FIELDS: list[Field] = [
    Field(name=col, dtype=pl.Float64, required=False) for col in _MEASURE_COLS
]


BDMEP_CONTRACT = DataContract(
    dataset_id="inmet-bdmep",
    fields=[*_METADATA_FIELDS, *_MEASURE_FIELDS],
    metadata={"source": "inmet", "granularity": "hourly"},
)
