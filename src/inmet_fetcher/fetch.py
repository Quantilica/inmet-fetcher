"""Fetching logic for INMET BDMEP data."""

from __future__ import annotations

import concurrent.futures
import datetime as dt
from pathlib import Path

from quantilica_core.http import HttpClient
from quantilica_core.logging import get_logger
import quantilica_core.metadata as core_meta

from .storage import InmetRepository

logger = get_logger(__name__)
client = HttpClient(timeout=60.0)


def expand_years(*years: str) -> list[int]:
    """Expand year strings like '2020:2022' or '2020' into a list of ints."""
    year_list = []
    for y in years:
        if ":" in y:
            start, end = y.split(":")
            year_list.extend(range(int(start), int(end) + 1))
        else:
            year_list.append(int(y))
    return year_list


def build_url(year: int) -> str:
    """Return the download URL for a given year."""
    return f"https://portal.inmet.gov.br/uploads/dadoshistoricos/{year}.zip"


_build_url = build_url


def _build_filename(year: int, last_modified: dt.datetime) -> str:
    return f"inmet-bdmep_{year}_{last_modified:%Y%m%d}.zip"


def _parse_last_modified(last_modified_str: str) -> dt.datetime:
    """Parse HTTP Last-Modified header string into datetime."""
    return dt.datetime.strptime(last_modified_str, "%a, %d %b %Y %H:%M:%S %Z")


def download_year(year: int, repo: InmetRepository) -> Path | None:
    """Download a single year's ZIP file using quantilica-core."""
    url = build_url(year)
    # Since we don't know the exact filename until we see the response or have an existing one,
    # we use a consistent name for the raw storage.
    target_path = repo.path_for_year(year, f"{year}.zip")
    
    try:
        return client.download_with_manifest(
            url,
            target_path,
            source_id="inmet",
            dataset_id="bdmep",
            producer="inmet-fetcher",
        )
    except Exception as exc:
        logger.error(f"Failed to download year {year}: {exc}")
        return None


def fetch(years: list[int], destdir: Path, workers: int = 4) -> list[Path]:
    """Fetch multiple years in parallel."""
    repo = InmetRepository(destdir)
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_year = {
            executor.submit(download_year, year, repo): year
            for year in years
        }
        for future in concurrent.futures.as_completed(future_to_year):
            path = future.result()
            if path:
                results.append(path)
    return sorted(results)


def generate_catalog(downloaded_files: list[Path]) -> core_meta.MetadataCatalog:
    """Generate a validated MetadataCatalog from a list of downloaded INMET ZIP files."""
    source_id = "inmet"
    source = core_meta.Source(
        id=source_id,
        name="INMET - Instituto Nacional de Meteorologia",
        homepage_url="https://portal.inmet.gov.br",
    )

    dataset_id = "bdmep"
    dataset = core_meta.Dataset(
        id=dataset_id,
        source_id=source_id,
        name="BDMEP - Banco de Dados Meteorológicos para Ensino e Pesquisa",
        description="Dados históricos anuais das estações meteorológicas brasileiras",
    )

    resources = []
    for file_path in downloaded_files:
        filename = file_path.name
        resource_id = filename.replace(".", "_")
        
        resources.append(
            core_meta.Resource(
                id=resource_id,
                dataset_id=dataset_id,
                name=filename,
                format="zip",
                path=str(file_path.absolute()),
            )
        )

    catalog = core_meta.MetadataCatalog(
        sources=[source],
        datasets=[dataset],
        resources=resources,
    )
    catalog.validate_references()
    return catalog
