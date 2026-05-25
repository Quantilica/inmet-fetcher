"""Tests for download_year and fetch using pytest-httpx."""

import datetime as dt

import httpx
import pytest

from inmet_fetcher.fetch import _build_url, download_year, fetch
from inmet_fetcher.storage import InmetRepository
from quantilica_core.storage import stamp_filename

FAKE_LAST_MODIFIED = "Mon, 01 Jan 2024 00:00:00 GMT"
FAKE_DATE = dt.date(2024, 1, 1)
FAKE_CONTENT = b"PK" + b"\x00" * 200  # 202 bytes, resembles a zip header


@pytest.fixture(autouse=True)
def fast_client(monkeypatch):
    from inmet_fetcher.fetch import client

    monkeypatch.setattr(client, "attempts", 1)
    monkeypatch.setattr(client, "retry_base_delay", 0)


def _expected_path(destdir, year):
    filename = stamp_filename(f"inmet-bdmep_{year}", "zip", FAKE_DATE)
    return InmetRepository(destdir).path_for_year(year, filename)


def _add_head(
    httpx_mock, year, *, last_modified=FAKE_LAST_MODIFIED, content_length=True
):
    """Add a HEAD mock response.

    ``content_length=True`` (default) → Content-Length: len(FAKE_CONTENT)
    ``content_length=False`` → omit Content-Length header
    ``content_length=<int>`` → use that value
    """
    headers = {}
    if content_length is True:
        headers["Content-Length"] = str(len(FAKE_CONTENT))
    elif content_length is not False:
        headers["Content-Length"] = str(content_length)
    if last_modified:
        headers["Last-Modified"] = last_modified
    httpx_mock.add_response(method="HEAD", url=_build_url(year), headers=headers)


# download_with_manifest always makes a HEAD request (freshness check, line 276 of http.py).
# If HEAD fails with FetchError and the file does not exist, the exception is swallowed
# and a GET is attempted anyway.  So per download_year() call:
#   new file:       _safe_head_date HEAD + download_with_manifest HEAD + GET
#   existing file:  _safe_head_date HEAD + download_with_manifest HEAD [+ GET if stale]
#   HEAD 404:       _safe_head_date HEAD 404 (caught) + download_with_manifest HEAD 404 (swallowed) + GET


class TestDownloadYear:
    def test_downloads_file(self, tmp_path, httpx_mock):
        _add_head(httpx_mock, 2023)  # _safe_head_date
        _add_head(httpx_mock, 2023)  # download_with_manifest freshness
        httpx_mock.add_response(
            method="GET", url=_build_url(2023), content=FAKE_CONTENT
        )

        result = download_year(2023, InmetRepository(tmp_path))

        assert result is not None
        assert result.exists()
        assert result.read_bytes() == FAKE_CONTENT

    def test_returns_correct_path(self, tmp_path, httpx_mock):
        _add_head(httpx_mock, 2023)
        _add_head(httpx_mock, 2023)
        httpx_mock.add_response(
            method="GET", url=_build_url(2023), content=FAKE_CONTENT
        )

        result = download_year(2023, InmetRepository(tmp_path))
        assert result == _expected_path(tmp_path, 2023)

    def test_creates_destdir(self, tmp_path, httpx_mock):
        destdir = tmp_path / "new" / "subdir"
        _add_head(httpx_mock, 2023)
        _add_head(httpx_mock, 2023)
        httpx_mock.add_response(
            method="GET", url=_build_url(2023), content=FAKE_CONTENT
        )

        download_year(2023, InmetRepository(destdir))
        assert destdir.exists()

    def test_skips_if_file_exists_with_same_size(self, tmp_path, httpx_mock):
        existing = _expected_path(tmp_path, 2023)
        existing.parent.mkdir(parents=True, exist_ok=True)
        existing.write_bytes(FAKE_CONTENT)

        # Both HEADs succeed; download_with_manifest sees file with same size → no GET
        _add_head(httpx_mock, 2023)
        _add_head(httpx_mock, 2023)

        result = download_year(2023, InmetRepository(tmp_path))

        assert result == existing
        requests = httpx_mock.get_requests()
        assert all(r.method != "GET" for r in requests)

    def test_redownloads_if_size_differs(self, tmp_path, httpx_mock):
        existing = _expected_path(tmp_path, 2023)
        existing.parent.mkdir(parents=True, exist_ok=True)
        existing.write_bytes(b"incomplete")

        # File exists with wrong size → HEAD ok → GET
        _add_head(httpx_mock, 2023)
        _add_head(httpx_mock, 2023)
        httpx_mock.add_response(
            method="GET", url=_build_url(2023), content=FAKE_CONTENT
        )

        result = download_year(2023, InmetRepository(tmp_path))
        assert result.read_bytes() == FAKE_CONTENT

    def test_returns_none_on_http_error(self, tmp_path, httpx_mock):
        # _safe_head_date HEAD → ConnectError → RetryError → caught by _safe_head_date
        # download_with_manifest HEAD → ConnectError → RetryError → propagates to outer except
        # (GET is never reached — RetryError is not a FetchError so it isn't swallowed)
        httpx_mock.add_exception(httpx.ConnectError("connection refused"))
        httpx_mock.add_exception(httpx.ConnectError("connection refused"))

        result = download_year(2023, InmetRepository(tmp_path))
        assert result is None

    def test_returns_none_when_head_fails(self, tmp_path, httpx_mock):
        # _safe_head_date HEAD 404 → FetchError → caught → None → bare filename
        # download_with_manifest HEAD 404 → FetchError → swallowed (file missing)
        # download_with_manifest GET 404 → FetchError → outer except → None
        httpx_mock.add_response(method="HEAD", url=_build_url(2023), status_code=404)
        httpx_mock.add_response(method="HEAD", url=_build_url(2023), status_code=404)
        httpx_mock.add_response(method="GET", url=_build_url(2023), status_code=404)

        result = download_year(2023, InmetRepository(tmp_path))
        assert result is None

    def test_handles_missing_last_modified_on_new_download(self, tmp_path, httpx_mock):
        _add_head(httpx_mock, 2023, last_modified=None)
        _add_head(httpx_mock, 2023, last_modified=None)
        httpx_mock.add_response(
            method="GET", url=_build_url(2023), content=FAKE_CONTENT
        )

        result = download_year(2023, InmetRepository(tmp_path))
        assert result is not None
        assert result.exists()

    def test_handles_missing_content_length(self, tmp_path, httpx_mock):
        _add_head(httpx_mock, 2023, content_length=False)
        _add_head(httpx_mock, 2023, content_length=False)
        httpx_mock.add_response(
            method="GET", url=_build_url(2023), content=FAKE_CONTENT
        )

        result = download_year(2023, InmetRepository(tmp_path))
        assert result is not None
        assert result.exists()


class TestFetch:
    def test_downloads_multiple_years(self, tmp_path, httpx_mock):
        years = [2021, 2022, 2023]
        for year in years:
            _add_head(httpx_mock, year)
            _add_head(httpx_mock, year)
            httpx_mock.add_response(
                method="GET", url=_build_url(year), content=FAKE_CONTENT
            )

        results = fetch(years, tmp_path, workers=2)
        assert len(results) == 3
        for path in results:
            assert path.exists()

    def test_returns_sorted_paths(self, tmp_path, httpx_mock):
        years = [2023, 2021, 2022]
        for year in years:
            _add_head(httpx_mock, year)
            _add_head(httpx_mock, year)
            httpx_mock.add_response(
                method="GET", url=_build_url(year), content=FAKE_CONTENT
            )

        results = fetch(years, tmp_path, workers=3)
        assert results == sorted(results)

    def test_skips_failed_years(self, tmp_path, httpx_mock):
        # 2022 succeeds
        _add_head(httpx_mock, 2022)
        _add_head(httpx_mock, 2022)
        httpx_mock.add_response(
            method="GET", url=_build_url(2022), content=FAKE_CONTENT
        )
        # 2023 fails: HEAD 404 (caught) → HEAD 404 (swallowed) → GET 404 → outer except
        httpx_mock.add_response(method="HEAD", url=_build_url(2023), status_code=404)
        httpx_mock.add_response(method="HEAD", url=_build_url(2023), status_code=404)
        httpx_mock.add_response(method="GET", url=_build_url(2023), status_code=404)

        results = fetch([2022, 2023], tmp_path, workers=2)
        assert len(results) == 1
        assert results[0] == _expected_path(tmp_path, 2022)

    def test_single_worker(self, tmp_path, httpx_mock):
        _add_head(httpx_mock, 2023)
        _add_head(httpx_mock, 2023)
        httpx_mock.add_response(
            method="GET", url=_build_url(2023), content=FAKE_CONTENT
        )

        results = fetch([2023], tmp_path, workers=1)
        assert len(results) == 1
