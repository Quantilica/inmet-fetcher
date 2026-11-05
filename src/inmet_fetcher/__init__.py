"""INMET BDMEP data client."""

from importlib.metadata import PackageNotFoundError, version

from .storage import DataRepository

try:
    __version__ = version("inmet-fetcher")
except PackageNotFoundError:
    __version__ = "0.0.0"

# Optional imports - only available if analysis extras are installed
try:
    from .reader import read, read_stations
    from .schema import BDMEP_CONTRACT

    _HAS_ANALYSIS = True
except ImportError:
    _HAS_ANALYSIS = False
    read = None
    read_stations = None
    BDMEP_CONTRACT = None

__all__ = [
    "__version__",
    "DataRepository",
]

if _HAS_ANALYSIS:
    __all__.extend(
        [
            "BDMEP_CONTRACT",
            "read",
            "read_stations",
        ]
    )
