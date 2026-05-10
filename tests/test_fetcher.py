"""Tests for download_year and fetch using pytest-httpx."""

import datetime as dt
import io
import zipfile

import httpx
import pytest

from inmet_fetcher.fetch import _build_filename, _build_url, download_year, fetch
from inmet_fetcher.storage import InmetRepository

@pytest.fixture(autouse=True)
def fast_client(monkeypatch):
    from inmet_fetcher.fetch import client
    monkeypatch.setattr(client, "attempts", 1)
    monkeypatch.setattr(client, "retry_base_delay", 0)

FAKE_LAST_MODIFIED = "Mon, 01 Jan 2024 00:00:00 GMT"
FAKE_LAST_MODIFIED_DT = dt.datetime(2024, 1, 1, 0, 0, 0)
FAKE_CONTENT = b"PK" + b"\x00" * 200  # 202 bytes, resembles a zip header


def _expected_path(destdir, year):
    return InmetRepository(destdir).path_for_year(year, f"{year}.zip")


class TestDownloadYear:
    def test_downloads_file(self, tmp_path, httpx_mock):
        httpx_mock.add_response(
            method="HEAD",
            url=_build_url(2023),
            headers={
                "Last-Modified": FAKE_LAST_MODIFIED,
                "Content-Length": str(len(FAKE_CONTENT)),
            },
        )
        httpx_mock.add_response(
            method="GET",
            url=_build_url(2023),
            content=FAKE_CONTENT,
        )

        result = download_year(2023, InmetRepository(tmp_path))

        assert result is not None
        assert result.exists()
        assert result.read_bytes() == FAKE_CONTENT

    def test_returns_correct_path(self, tmp_path, httpx_mock):
        httpx_mock.add_response(
            method="HEAD",
            url=_build_url(2023),
            headers={
                "Last-Modified": FAKE_LAST_MODIFIED,
                "Content-Length": str(len(FAKE_CONTENT)),
            },
        )
        httpx_mock.add_response(
            method="GET",
            url=_build_url(2023),
            content=FAKE_CONTENT,
        )

        result = download_year(2023, InmetRepository(tmp_path))
        assert result == _expected_path(tmp_path, 2023)

    def test_creates_destdir(self, tmp_path, httpx_mock):
        destdir = tmp_path / "new" / "subdir"
        httpx_mock.add_response(
            method="HEAD",
            url=_build_url(2023),
            headers={
                "Last-Modified": FAKE_LAST_MODIFIED,
                "Content-Length": str(len(FAKE_CONTENT)),
            },
        )
        httpx_mock.add_response(
            method="GET",
            url=_build_url(2023),
            content=FAKE_CONTENT,
        )

        download_year(2023, InmetRepository(destdir))
        assert destdir.exists()

    def test_skips_if_file_exists_with_same_size(self, tmp_path, httpx_mock):
        existing = _expected_path(tmp_path, 2023)
        existing.parent.mkdir(parents=True, exist_ok=True)
        existing.write_bytes(FAKE_CONTENT)

        httpx_mock.add_response(
            method="HEAD",
            url=_build_url(2023),
            headers={
                "Last-Modified": FAKE_LAST_MODIFIED,
                "Content-Length": str(len(FAKE_CONTENT)),
            },
        )

        # Mock the download if it were to happen, but we expect it to be skipped.
        # Actually download_with_manifest might still do a HEAD request.

        result = download_year(2023, InmetRepository(tmp_path))

        assert result == existing
        # Only HEAD was made — no GET. If GET were made, httpx_mock would raise.
        requests = httpx_mock.get_requests()
        # HttpClient.download_with_manifest might do more than one HEAD if it follows redirects, etc.
        # But definitely no GET if it skips.
        assert all(r.method != "GET" for r in requests)

    def test_redownloads_if_size_differs(self, tmp_path, httpx_mock):
        existing = _expected_path(tmp_path, 2023)
        existing.parent.mkdir(parents=True, exist_ok=True)
        existing.write_bytes(b"incomplete")  # wrong size

        httpx_mock.add_response(
            method="HEAD",
            url=_build_url(2023),
            headers={
                "Last-Modified": FAKE_LAST_MODIFIED,
                "Content-Length": str(len(FAKE_CONTENT)),
            },
        )
        httpx_mock.add_response(
            method="GET",
            url=_build_url(2023),
            content=FAKE_CONTENT,
        )

        result = download_year(2023, InmetRepository(tmp_path))
        assert result.read_bytes() == FAKE_CONTENT

    def test_returns_none_on_http_error(self, tmp_path, httpx_mock):
        httpx_mock.add_exception(httpx.ConnectError("connection refused"))

        result = download_year(2023, InmetRepository(tmp_path))
        assert result is None

    def test_returns_none_when_head_fails(self, tmp_path, httpx_mock):
        httpx_mock.add_response(
            method="HEAD",
            url=_build_url(2023),
            status_code=404,
        )
        httpx_mock.add_response(
            method="GET",
            url=_build_url(2023),
            status_code=404,
        )

        result = download_year(2023, InmetRepository(tmp_path))
        assert result is None

    def test_handles_missing_last_modified_on_new_download(self, tmp_path, httpx_mock):
        httpx_mock.add_response(
            method="HEAD",
            url=_build_url(2023),
            headers={"Content-Length": str(len(FAKE_CONTENT))},
        )
        httpx_mock.add_response(
            method="GET",
            url=_build_url(2023),
            content=FAKE_CONTENT,
        )
        
        result = download_year(2023, InmetRepository(tmp_path))
        assert result is not None
        assert result.exists()

    def test_handles_missing_content_length(self, tmp_path, httpx_mock):
        httpx_mock.add_response(
            method="HEAD",
            url=_build_url(2023),
            headers={"Last-Modified": FAKE_LAST_MODIFIED},  # no Content-Length
        )
        httpx_mock.add_response(
            method="GET",
            url=_build_url(2023),
            content=FAKE_CONTENT,
        )

        result = download_year(2023, InmetRepository(tmp_path))
        assert result is not None
        assert result.exists()


class TestFetch:
    def test_downloads_multiple_years(self, tmp_path, httpx_mock):
        years = [2021, 2022, 2023]
        for year in years:
            httpx_mock.add_response(
                method="HEAD",
                url=_build_url(year),
                headers={
                    "Last-Modified": FAKE_LAST_MODIFIED,
                    "Content-Length": str(len(FAKE_CONTENT)),
                },
            )
            httpx_mock.add_response(
                method="GET",
                url=_build_url(year),
                content=FAKE_CONTENT,
            )

        results = fetch(years, tmp_path, workers=2)
        assert len(results) == 3
        for path in results:
            assert path.exists()

    def test_returns_sorted_paths(self, tmp_path, httpx_mock):
        years = [2023, 2021, 2022]
        for year in years:
            httpx_mock.add_response(
                method="HEAD",
                url=_build_url(year),
                headers={
                    "Last-Modified": FAKE_LAST_MODIFIED,
                    "Content-Length": str(len(FAKE_CONTENT)),
                },
            )
            httpx_mock.add_response(
                method="GET",
                url=_build_url(year),
                content=FAKE_CONTENT,
            )

        results = fetch(years, tmp_path, workers=3)
        assert results == sorted(results)

    def test_skips_failed_years(self, tmp_path, httpx_mock):
        httpx_mock.add_response(
            method="HEAD",
            url=_build_url(2022),
            headers={
                "Last-Modified": FAKE_LAST_MODIFIED,
                "Content-Length": str(len(FAKE_CONTENT)),
            },
        )
        httpx_mock.add_response(
            method="GET",
            url=_build_url(2022),
            content=FAKE_CONTENT,
        )
        # 2023 will fail — 404 on HEAD and GET
        httpx_mock.add_response(
            method="HEAD",
            url=_build_url(2023),
            status_code=404,
        )
        httpx_mock.add_response(
            method="GET",
            url=_build_url(2023),
            status_code=404,
        )

        results = fetch([2022, 2023], tmp_path, workers=2)
        assert len(results) == 1
        assert results[0] == _expected_path(tmp_path, 2022)

    def test_single_worker(self, tmp_path, httpx_mock):
        httpx_mock.add_response(
            method="HEAD",
            url=_build_url(2023),
            headers={
                "Last-Modified": FAKE_LAST_MODIFIED,
                "Content-Length": str(len(FAKE_CONTENT)),
            },
        )
        httpx_mock.add_response(
            method="GET",
            url=_build_url(2023),
            content=FAKE_CONTENT,
        )

        results = fetch([2023], tmp_path, workers=1)
        assert len(results) == 1
