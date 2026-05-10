"""Data repository management for INMET BDMEP."""

from __future__ import annotations

import os
from pathlib import Path

from quantilica_core.storage import BaseDataRepository


class InmetRepository(BaseDataRepository):
    """Repository for INMET BDMEP weather data."""

    def __init__(self, root: str | os.PathLike[str]) -> None:
        super().__init__(root)

    def path_for_year(self, year: int, filename: str) -> Path:
        """Return the path for a specific year's ZIP file."""
        return self.raw_path("bdmep", str(year), filename)
