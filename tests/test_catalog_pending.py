"""Marca ``pending_publication`` do ano corrente no catálogo."""

from __future__ import annotations

import datetime as dt

from inmet_fetcher.catalog import PENDING_GRACE_DAYS, list_datasets


def _pending_years(today: dt.date) -> list[int]:
    return [
        e["year"]
        for e in list_datasets("bdmep", today=today)
        if e.get("pending_publication")
    ]


def test_1o_de_janeiro_marca_so_o_ano_novo() -> None:
    entries = list_datasets("bdmep", today=dt.date(2027, 1, 1))
    assert [e["year"] for e in entries][-2:] == [2026, 2027]
    assert entries[-1]["url"].endswith("/2027.zip")
    assert _pending_years(dt.date(2027, 1, 1)) == [2027]


def test_a_marca_acaba_depois_da_folga() -> None:
    last = dt.date(2027, 1, 1) + dt.timedelta(days=PENDING_GRACE_DAYS)
    assert _pending_years(last) == [2027]
    assert _pending_years(last + dt.timedelta(days=1)) == []


def test_meio_do_ano_nao_marca_nada_e_anos_fechados_nunca() -> None:
    assert _pending_years(dt.date(2026, 11, 28)) == []
    # na folga de 2027, o ano fechado de 2026 continua sem marca
    entries = list_datasets("bdmep", today=dt.date(2027, 2, 1))
    assert not [e for e in entries if e["year"] < 2027 and "pending_publication" in e]


def test_grupo_desconhecido_segue_vazio() -> None:
    assert list_datasets("outro", today=dt.date(2027, 1, 1)) == []
