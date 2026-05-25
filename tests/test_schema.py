"""Schema-regression tests for BDMEP_CONTRACT.

These guard against silent breakage of the Parquet contract: if the
upstream CSV layout changes a column name or dtype, ``validate()``
fails fast here instead of producing a corrupt Parquet.
"""

import datetime as dt

import polars as pl
import pytest

from inmet_fetcher import BDMEP_CONTRACT
from inmet_fetcher.reader import _MEASURE_COLS


def _make_valid_frame() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "regiao": ["Norte"],
            "uf": ["AM"],
            "estacao": ["Manaus"],
            "codigo_wmo": ["A001"],
            "latitude": [-3.103],
            "longitude": [-60.016],
            "altitude": [48.0],
            "data_fundacao": [dt.datetime(1990, 6, 15)],
            "data_hora": [dt.datetime(2023, 1, 1, 0, 0)],
            **{col: [0.0] for col in _MEASURE_COLS},
        }
    )


class TestBdmepContractValidate:
    def test_accepts_valid_frame(self):
        BDMEP_CONTRACT.validate(_make_valid_frame())

    def test_rejects_missing_required_field(self):
        df = _make_valid_frame().drop("data_hora")
        with pytest.raises(ValueError, match="data_hora"):
            BDMEP_CONTRACT.validate(df)

    def test_rejects_wrong_dtype(self):
        df = _make_valid_frame().with_columns(pl.col("latitude").cast(pl.Utf8))
        with pytest.raises(TypeError, match="latitude"):
            BDMEP_CONTRACT.validate(df)

    def test_optional_field_can_be_missing(self):
        df = _make_valid_frame().drop("data_fundacao")
        BDMEP_CONTRACT.validate(df)

    def test_validates_lazy_frame(self):
        BDMEP_CONTRACT.validate(_make_valid_frame().lazy())

    def test_contract_dataset_id(self):
        assert BDMEP_CONTRACT.dataset_id == "inmet-bdmep"

    def test_all_measure_cols_in_contract(self):
        names = {f.name for f in BDMEP_CONTRACT.fields}
        for col in _MEASURE_COLS:
            assert col in names


class TestBdmepContractCast:
    def test_cast_unifies_types(self):
        df = pl.DataFrame(
            {
                "regiao": ["Norte"],
                "uf": ["AM"],
                "estacao": ["Manaus"],
                "codigo_wmo": ["A001"],
                "data_hora": [dt.datetime(2023, 1, 1)],
                "latitude": [-3],  # int, contract expects Float64
                **{col: [0] for col in _MEASURE_COLS},
            }
        )
        casted = BDMEP_CONTRACT.cast(df)
        assert casted.schema["latitude"] == pl.Float64
        assert casted.schema["temperatura_ar"] == pl.Float64
