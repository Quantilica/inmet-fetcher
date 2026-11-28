"""HEAD de frescor do ``sync``: orçamento curto e fonte fora do ar."""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any

import httpx2
import pytest
from quantilica.core.exceptions import FetchError
from quantilica.core.http import HttpClient

from inmet_fetcher import plugin
from inmet_fetcher.plugin import fetcher

URL = "https://inmet.test/uploads/dadoshistoricos/2026.zip"


def _client(handler: Any, *, timeout: float = 180.0, attempts: int = 5) -> HttpClient:
    return HttpClient(
        timeout=timeout,
        attempts=attempts,
        retry_base_delay=0.0,
        transport=httpx2.MockTransport(handler),
    )


def test_orcamento_do_head_e_menor_que_o_do_download() -> None:
    assert plugin.PROBE_TIMEOUT < 180.0
    assert plugin.PROBE_ATTEMPTS < 5


def test_head_usa_o_timeout_curto_dentro_do_with(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O timeout efetivo do httpx, já dentro do ``with``, é o da sonda."""
    visto: dict[str, Any] = {}

    class Espiao(HttpClient):
        def head_or_get(self, url: str, **kwargs: Any) -> Any:
            assert self._client is not None  # dentro do ``with``
            visto["timeout"] = self._client.timeout
            visto["attempts"] = self.attempts
            return super().head_or_get(url, **kwargs)

    def fake_default_client() -> HttpClient:
        return Espiao(
            timeout=180.0,
            attempts=5,
            transport=httpx2.MockTransport(lambda req: httpx2.Response(200)),
        )

    monkeypatch.setattr(plugin, "default_client", fake_default_client)
    assert plugin._head_last_modified(URL) is None
    assert visto["timeout"].connect == plugin.PROBE_TIMEOUT
    assert visto["timeout"].read == plugin.PROBE_TIMEOUT
    assert visto["attempts"] == plugin.PROBE_ATTEMPTS


def test_valor_menor_do_ambiente_nao_e_aumentado(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        plugin,
        "default_client",
        lambda: _client(lambda r: httpx2.Response(200), timeout=5.0, attempts=1),
    )
    client = plugin._probe_client()
    assert (client.timeout, client.attempts) == (5.0, 1)


def test_last_modified_vira_a_data_do_carimbo(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(
            200, headers={"Last-Modified": "Sat, 31 Oct 2026 12:00:00 GMT"}
        )

    monkeypatch.setattr(plugin, "default_client", lambda: _client(handler))
    assert plugin._head_last_modified(URL) == dt.date(2026, 10, 31)


@pytest.mark.parametrize("status", [404, 500, 503])
def test_status_de_erro_no_head_nao_levanta(
    monkeypatch: pytest.MonkeyPatch, status: int
) -> None:
    """404/5xx no HEAD: sem data, e o download decide (404 vira pendente/erro)."""
    monkeypatch.setattr(
        plugin, "default_client", lambda: _client(lambda r: httpx2.Response(status))
    )
    assert plugin._head_last_modified(URL) is None


def test_fonte_fora_do_ar_falha_o_head_sem_tentar_o_download(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    chamadas: list[str] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        chamadas.append(request.method)
        raise httpx2.ConnectTimeout("sem conexão", request=request)

    monkeypatch.setattr(plugin, "default_client", lambda: _client(handler))
    monkeypatch.setattr(fetcher, "client", _client(handler))

    with pytest.raises(FetchError, match="fonte inacessível"):
        plugin._head_last_modified(URL)
    assert chamadas == ["HEAD"] * plugin.PROBE_ATTEMPTS

    # pelo sync: o arquivo vira erro nomeado e o download (5 tentativas de
    # 180 s) nem começa: só as tentativas do HEAD chegam ao transporte
    chamadas.clear()
    entry = {
        "id": "bdmep-2026",
        "group": "bdmep",
        "year": 2026,
        "url": URL,
        "ext": "zip",
    }
    done, total, errors = fetcher.download_datasets([entry], tmp_path, workers=1)
    assert (done, total) == (0, 1)
    assert [e[0] for e in errors] == ["bdmep-2026"]
    assert "fonte inacessível" in errors[0][1]
    assert set(chamadas) == {"HEAD"}
    assert len(chamadas) == plugin.PROBE_ATTEMPTS
