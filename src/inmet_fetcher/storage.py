"""Data repository management for INMET BDMEP."""

from __future__ import annotations

import datetime as dt
import os
from pathlib import Path
from typing import Any

from quantilica.core.storage import BaseDataRepository, build_stamped_filename


class DataRepository(BaseDataRepository):
    """Repository for INMET BDMEP weather data."""

    def __init__(self, root: str | os.PathLike[str]) -> None:
        """Initialize the data repository.

        Args:
            root: The root directory for the repository.
        """
        super().__init__(root)

    def path_for_year(self, year: int, filename: str) -> Path:
        """Return the path for a specific year's ZIP file.

        Args:
            year: The year of the dataset.
            filename: The name of the file.

        Returns:
            The full Path where the file should be stored.
        """
        return self.dataset_path("bdmep", str(year), filename)

    def path_for_entry(
        self,
        entry: dict[str, Any],
        *,
        last_modified: dt.date | None = None,
    ) -> Path:
        """Compute the local path for a dataset entry.

        Args:
            entry: The dataset entry metadata.
            last_modified: The last modified date, if any.

        Returns:
            The Path where the dataset entry file should be stored.
        """
        year = entry["year"]
        timestamp = last_modified or dt.date.today()
        filename = build_stamped_filename(
            "inmet-bdmep", year, ext=entry["ext"], timestamp=timestamp
        )
        return self.path_for_year(year, filename)
