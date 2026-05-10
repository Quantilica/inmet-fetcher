"""INMET BDMEP data client."""

from .fetch import expand_years, fetch, generate_catalog
from .reader import read, read_stations
from .storage import InmetRepository

__version__ = "0.2.0"
__all__ = [
    "expand_years",
    "fetch",
    "generate_catalog",
    "read",
    "read_stations",
    "InmetRepository",
]
