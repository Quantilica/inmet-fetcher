"""INMET BDMEP data client."""

from importlib.metadata import PackageNotFoundError, version

from .fetch import expand_years, fetch, generate_catalog
from .reader import read, read_stations
from .storage import InmetRepository

try:
    __version__ = version("inmet-fetcher")
except PackageNotFoundError:
    __version__ = "0.0.0"
__all__ = [
    "expand_years",
    "fetch",
    "generate_catalog",
    "read",
    "read_stations",
    "InmetRepository",
]
