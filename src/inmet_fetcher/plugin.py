"""Typer plugin for quantilica-cli integration."""

from __future__ import annotations

import datetime as dt
import email.utils
import logging
from pathlib import Path
from typing import Any

import httpx2
from quantilica.cli.sdk import FetcherApp, default_client
from quantilica.core.exceptions import FetchError
from quantilica.core.registry import FetcherInfo
from quantilica.core.sync import FreshnessPolicy

from .catalog import GROUP_ALIASES, GROUPS, list_datasets
from .storage import DataRepository

logger = logging.getLogger(__name__)

# HEAD de frescor (carimbo do nome do arquivo): orçamento curto, bem menor que o do
# download (180 s e 5 tentativas por padrão no cliente do host, ajustáveis por
# ``QUANTILICA_HTTP_*``). Com a fonte fora do ar, cada arquivo gastava
# 5 x 180 s no HEAD e outro tanto no download: 27 arquivos em 4 threads ficaram
# 5,5 h presos. Agora o HEAD desiste em ~1 min e, se nem a conexão se faz, o
# arquivo falha sem tentar o download. O orçamento do download não muda.
PROBE_TIMEOUT = 30.0
PROBE_ATTEMPTS = 2
PROBE_RETRY_DELAY = 1.0


def path_builder(
    output_dir: Path, entry: dict[str, Any], last_modified: dt.date | None
) -> Path:
    """Build the local file path for a downloaded dataset entry.

    Args:
        output_dir: Base directory where data is stored.
        entry: Dataset entry dictionary containing metadata like year and ext.
        last_modified: Optional last modified date to include in the filename.

    Returns:
        Path to the local file for the dataset.
    """
    return DataRepository(output_dir).path_for_entry(entry, last_modified=last_modified)


def _probe_client() -> Any:
    """Cliente padrão do host com o orçamento curto do HEAD de frescor."""
    client = default_client()
    # Antes de abrir o ``with``: o ``__enter__`` monta o cliente httpx com o
    # timeout que o objeto tem naquele momento, e mudar depois não o alcança.
    # ``min`` respeita um valor ainda menor fixado por ``QUANTILICA_HTTP_*``.
    client.timeout = min(client.timeout, PROBE_TIMEOUT)
    client.attempts = min(client.attempts, PROBE_ATTEMPTS)
    client.retry_base_delay = min(client.retry_base_delay, PROBE_RETRY_DELAY)
    return client


def _connect_failure(exc: BaseException | None) -> BaseException | None:
    """Achar, na cadeia da exceção, a falha de CONEXÃO (não de resposta).

    O cliente do core esgota as tentativas e levanta ``RetryError`` com a última
    falha em ``__cause__``; por isso a cadeia é percorrida.
    """
    seen: set[int] = set()
    while exc is not None and id(exc) not in seen:
        if isinstance(exc, httpx2.ConnectTimeout | httpx2.ConnectError):
            return exc
        seen.add(id(exc))
        exc = exc.__cause__ or exc.__context__
    return None


def _head_last_modified(url: str) -> dt.date | None:
    """Data do ``Last-Modified`` por um HEAD rápido, ou ``None`` se indisponível.

    Falha de HEAD (status de erro, resposta lenta, servidor sem HEAD) não impede o
    download: devolve ``None`` e o nome usa a data do dia, como antes. Só a
    impossibilidade de CONECTAR (a fonte fora do ar) levanta ``FetchError``: o
    download teria o mesmo destino, depois de muito mais espera.

    Args:
        url: URL do arquivo.

    Returns:
        A data do ``Last-Modified``, ou ``None``.

    Raises:
        FetchError: Se a conexão com a fonte não se estabelece.
    """
    with _probe_client() as client:
        try:
            response = client.head_or_get(url)
        except Exception as exc:  # noqa: BLE001 - frescor é melhor esforço
            cause = _connect_failure(exc)
            if cause is not None:
                raise FetchError(
                    f"fonte inacessível (sem conexão em {PROBE_ATTEMPTS} "
                    f"tentativas de {PROBE_TIMEOUT:.0f} s): {url}: {cause!r}"
                ) from exc
            logger.warning("HEAD de frescor falhou para %s: %r", url, exc)
            return None
    value = response.headers.get("Last-Modified")
    if not value:
        return None
    try:
        return email.utils.parsedate_to_datetime(value).date()
    except (TypeError, ValueError):
        return None


class _InmetFetcherApp(FetcherApp):
    """``FetcherApp`` com o HEAD de frescor do ``sync`` de orçamento curto."""

    def _safe_head_date(self, url: str) -> dt.date | None:
        if self.freshness_policy == FreshnessPolicy.REMOTE_ONLY:
            return None
        return _head_last_modified(url)


fetcher = _InmetFetcherApp(
    name="inmet-fetcher",
    help="Dados meteorológicos do INMET-BDMEP.",
    info=FetcherInfo(
        id="inmet",
        nome="INMET - Banco de Dados Meteorológicos (BDMEP)",
        orgao="Instituto Nacional de Meteorologia (INMET)",
        licenca=(
            "Sem licença declarada; dados públicos pela Lei 12.527/2011 (LAI) "
            "e Decreto 8.777/2016"
        ),
        homepage="https://portal.inmet.gov.br/dadoshistoricos",
        cadencia="monthly",
        dominio="agropecuaria",
    ),
    groups_dict=GROUPS,
    aliases_dict=GROUP_ALIASES,
    list_datasets=list_datasets,
    path_builder=path_builder,
    default_output=Path("/data/inmet"),
    freshness_policy=FreshnessPolicy.HEAD_OR_MANIFEST,
)


def convert(
    input_dir: Path,
    lake_dir: Path,
    *,
    dataset: list[str] | None = None,
    force: bool = False,
) -> Any:
    """Converte arquivos brutos do INMET para o lake Hive (Parquet)."""
    try:
        from inmet_fetcher import lake
    except ImportError as exc:
        raise ImportError(
            "Conversão para o lake requer o extra 'analysis'. "
            "Instale com: quantilica install inmet --extra analysis"
        ) from exc

    return lake.converter.convert(input_dir, lake_dir, datasets=dataset, force=force)


fetcher.command_convert(convert)
fetcher.command_pipeline(convert)

app = fetcher.app
