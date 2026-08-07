"""INMET BDMEP data client."""

from importlib.metadata import PackageNotFoundError, version

from .reader import read, read_stations
from .schema import BDMEP_CONTRACT
from .storage import DataRepository
from .writer import write_to_parquet

try:
    __version__ = version("inmet-fetcher")
except PackageNotFoundError:
    __version__ = "0.0.0"
__all__ = [
    "__version__",
    "read",
    "read_stations",
    "DataRepository",
    "write_to_parquet",
    "BDMEP_CONTRACT",
]
