"""Versões carimbadas do mesmo ZIP anual: só a vigente vira Parquet.

O bruto guarda ``bdmep-2015@20261101.zip``, ``bdmep-2015@20261102.zip``...; todas
mapeiam para o mesmo Parquet. O conversor escolhe a vigente (``select_current``)
antes de abrir qualquer ZIP.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

pytest.importorskip("quantilica.analytics.lake")
pytest.importorskip("duckdb")

from quantilica.analytics.lake import scan_dataset  # noqa: E402

import inmet_fetcher.lake as lake_mod  # noqa: E402
from inmet_fetcher.lake import DATASET_ID, SOURCE_ID, converter  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"
CSV_A = FIXTURES / "INMET_CO_DF_A001_BRASILIA_01-01-2015_A_31-12-2015.CSV"
CSV_B = FIXTURES / "INMET_NE_BA_A438_MARAU_01-01-2022_A_31-12-2022.CSV"


def _zip(path: Path, *csvs: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as z:
        for csv in csvs:
            z.write(csv, arcname=csv.name)
    return path


def _linhas(lake: Path) -> int:
    return scan_dataset(lake / SOURCE_ID / DATASET_ID).collect().height


@pytest.fixture
def aberturas(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    vistas: list[str] = []
    original = lake_mod.read_zipfile

    def espia(path: Path, *args, **kwargs):  # noqa: ANN002, ANN003, ANN202
        vistas.append(Path(path).name)
        return original(path, *args, **kwargs)

    monkeypatch.setattr(lake_mod, "read_zipfile", espia)
    return vistas


def test_so_a_vigente_e_convertida(tmp_path: Path, aberturas: list[str]) -> None:
    raw, lake = tmp_path / "raw", tmp_path / "lake"
    _zip(raw / "bdmep-2015@20261101.zip", CSV_A)
    _zip(raw / "bdmep-2015@20261102.zip", CSV_A, CSV_B)

    res = converter.convert(raw, lake)
    assert (res.converted, res.skipped, res.errors) == (1, 1, [])
    assert aberturas == ["bdmep-2015@20261102.zip"]

    # segunda rodada: nada é reconvertido nem aberto
    aberturas.clear()
    res2 = converter.convert(raw, lake)
    assert (res2.converted, res2.skipped, res2.errors) == (0, 2, [])
    assert aberturas == []


def test_versao_nova_converte_so_ela_e_substitui_sem_duplicar(
    tmp_path: Path, aberturas: list[str]
) -> None:
    raw, lake = tmp_path / "raw", tmp_path / "lake"
    _zip(raw / "bdmep-2015@20261101.zip", CSV_A)
    converter.convert(raw, lake)
    antes = _linhas(lake)

    _zip(raw / "bdmep-2015@20261102.zip", CSV_A, CSV_B)
    aberturas.clear()
    res = converter.convert(raw, lake)
    assert (res.converted, res.skipped, res.errors) == (1, 1, [])
    assert aberturas == ["bdmep-2015@20261102.zip"]

    assert len(list((lake / SOURCE_ID / DATASET_ID).rglob("*.parquet"))) == 1
    # linhas da versão nova (CSV_A + CSV_B), sem sobra da antiga
    limpo = tmp_path / "lake-limpo"
    solo = tmp_path / "raw-solo"
    _zip(solo / "bdmep-2015@20261102.zip", CSV_A, CSV_B)
    converter.convert(solo, limpo)
    assert _linhas(lake) == _linhas(limpo)
    assert _linhas(lake) > antes


def test_sem_carimbo_perde_para_o_carimbado(
    tmp_path: Path, aberturas: list[str]
) -> None:
    raw, lake = tmp_path / "raw", tmp_path / "lake"
    _zip(raw / "bdmep-2015.zip", CSV_A)
    _zip(raw / "bdmep-2015@20261102.zip", CSV_A, CSV_B)
    res = converter.convert(raw, lake)
    assert (res.converted, res.skipped, res.errors) == (1, 1, [])
    assert aberturas == ["bdmep-2015@20261102.zip"]


def test_anos_diferentes_sao_arquivos_diferentes(
    tmp_path: Path, aberturas: list[str]
) -> None:
    raw, lake = tmp_path / "raw", tmp_path / "lake"
    _zip(raw / "bdmep-2015@20261101.zip", CSV_A)
    _zip(raw / "bdmep-2016@20261101.zip", CSV_A)
    res = converter.convert(raw, lake)
    assert (res.converted, res.skipped, res.errors) == (2, 0, [])
