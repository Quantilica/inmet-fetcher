"""Política de frescor declarada e estabilidade do nome com Last-Modified (W3-POL).

``REMOTE_ONLY`` (F3) descarta o Last-Modified e o nome do arquivo cai em ``@hoje``:
fontes que expõem Last-Modified/ETag seriam re-baixadas todo dia. Estes testes
(offline) travam a política declarada e garantem que, com ``last_modified``
fornecido, o nome carrega ``@<data do Last-Modified>`` e não muda de um dia para o
outro.
"""

from __future__ import annotations

import datetime as dt
import types
from pathlib import Path

import pytest
from quantilica.core.sync import FreshnessPolicy

from inmet_fetcher import storage as storage_module
from inmet_fetcher.plugin import fetcher
from inmet_fetcher.storage import DataRepository

_LAST_MODIFIED = dt.date(2026, 10, 28)


class _AnyDate(type):
    """Metaclasse que mantém ``isinstance(x, dt.date)`` verdadeiro para datas reais."""

    def __instancecheck__(cls, obj: object) -> bool:
        return isinstance(obj, dt.date)


def _frozen_dt(today: dt.date) -> types.SimpleNamespace:
    """Substitui o módulo ``datetime`` do storage com ``date.today()`` fixo."""

    class _FrozenDate(dt.date, metaclass=_AnyDate):
        @classmethod
        def today(cls) -> dt.date:
            return today

    return types.SimpleNamespace(
        date=_FrozenDate,
        datetime=dt.datetime,
        time=dt.time,
        timedelta=dt.timedelta,
        timezone=dt.timezone,
    )


def _build_path(root: Path, last_modified: dt.date) -> Path:
    entry = {"year": 2024, "ext": "zip"}
    return DataRepository(root).path_for_entry(entry, last_modified=last_modified)


def test_freshness_policy_declared() -> None:
    assert fetcher.freshness_policy == FreshnessPolicy.HEAD_OR_MANIFEST
    assert fetcher.freshness_policy != FreshnessPolicy.REMOTE_ONLY


def test_name_stable_across_days_with_last_modified(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Com ``last_modified`` o nome usa ``@<Last-Modified>`` e independe do dia."""
    monkeypatch.setattr(storage_module, "dt", _frozen_dt(dt.date(2026, 11, 3)))
    day_one = _build_path(tmp_path, _LAST_MODIFIED)
    monkeypatch.setattr(storage_module, "dt", _frozen_dt(dt.date(2026, 11, 4)))
    day_two = _build_path(tmp_path, _LAST_MODIFIED)

    assert day_one == day_two
    assert f"@{_LAST_MODIFIED:%Y%m%d}" in day_one.name
    assert "@20261103" not in day_one.name
    assert "@20261104" not in day_two.name
