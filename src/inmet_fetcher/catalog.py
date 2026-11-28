"""INMET BDMEP unified dataset catalog."""

import datetime as dt
from typing import Any

GROUPS = {
    "bdmep": {
        "name": "Banco de Dados Meteorológicos para Ensino e Pesquisa",
    }
}

GROUP_ALIASES: dict[str, list[str]] = {}

# O ZIP do ano corrente é republicado ao longo do ano ("Até <data de corte>") e
# só passa a existir depois do primeiro fechamento de mês. Até lá, o servidor
# responde 404 para ``<ano>.zip``. A entrada do ano corrente leva
# ``pending_publication`` (o 404 vira "ainda não publicado", sem erro) durante
# esta folga, contada desde 1º de janeiro: ~1º de abril, com margem sobre o
# primeiro fechamento (fim de janeiro) e o atraso de republicação (cerca de uma
# semana após o corte, observado em 2026-11). Passada a folga, o 404 volta a ser
# erro: nome errado não vira silêncio. Estimativa, não medida: ajuste se o INMET
# publicar mais tarde.
PENDING_GRACE_DAYS = 90


def list_datasets(
    group: str | None = None, *, today: dt.date | None = None
) -> list[dict[str, Any]]:
    """List available INMET BDMEP datasets for download.

    Args:
        group: Optional group name to filter. If provided and not 'bdmep',
            returns empty list.
        today: Reference day (default: today); exists for tests.

    Returns:
        List of dictionaries containing dataset metadata (id, group, year, url, ext).
        The current year's entry carries ``pending_publication`` while it may
        not be published yet (see ``PENDING_GRACE_DAYS``).
    """
    if group is not None and group != "bdmep":
        return []
    today = today or dt.date.today()
    current_year = today.year
    pending_until = dt.date(current_year, 1, 1) + dt.timedelta(days=PENDING_GRACE_DAYS)
    entries = []
    for year in range(2000, current_year + 1):
        entry: dict[str, Any] = {
            "id": f"bdmep-{year}",
            "group": "bdmep",
            "year": year,
            "url": f"https://portal.inmet.gov.br/uploads/dadoshistoricos/{year}.zip",
            "ext": "zip",
        }
        if year == current_year and today <= pending_until:
            entry["pending_publication"] = True
        entries.append(entry)
    return entries
