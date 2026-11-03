"""Tests for storage module."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

from inmet_fetcher.storage import DataRepository


class TestPathForEntry:
    """Tests for DataRepository.path_for_entry method."""

    def test_path_for_entry_with_last_modified(self, tmp_path: Path) -> None:
        """Test path_for_entry with explicit last_modified date."""
        repo = DataRepository(tmp_path)
        entry = {"year": 2024, "ext": "zip"}
        last_modified = dt.date(2024, 3, 15)

        path = repo.path_for_entry(entry, last_modified=last_modified)

        assert "inmet-bdmep_2024@20240315.zip" in str(path)
        assert path.parent.name == "2024"

    def test_path_for_entry_fallback_timestamp(self, tmp_path: Path) -> None:
        """Test path_for_entry falls back to today's date when last_modified is None."""
        repo = DataRepository(tmp_path)
        entry = {"year": 2024, "ext": "zip"}
        today = dt.date.today()

        path = repo.path_for_entry(entry, last_modified=None)

        expected_timestamp = today.strftime("%Y%m%d")
        assert f"inmet-bdmep_2024@{expected_timestamp}.zip" in str(path)
        assert path.parent.name == "2024"

    def test_path_for_entry_today_explicit(self, tmp_path: Path) -> None:
        """Test path_for_entry with explicit today date matches fallback."""
        repo = DataRepository(tmp_path)
        entry = {"year": 2024, "ext": "zip"}
        today = dt.date.today()

        path_explicit = repo.path_for_entry(entry, last_modified=today)
        path_fallback = repo.path_for_entry(entry, last_modified=None)

        assert str(path_explicit) == str(path_fallback)
