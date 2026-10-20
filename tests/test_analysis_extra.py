"""Tests for inmet_fetcher analysis-extra import guard."""

import importlib
import sys

import pytest

MODULES = [
    "inmet_fetcher.reader",
    "inmet_fetcher.schema",
    "inmet_fetcher.writer",
]


def test_analysis_extra_mensagem_acionavel():
    salvo_polars = sys.modules.get("polars")
    try:
        for module_name in MODULES:
            sys.modules["polars"] = None
            sys.modules.pop(module_name, None)
            try:
                with pytest.raises(ImportError, match="requer o extra 'analysis'"):
                    importlib.import_module(module_name)
            finally:
                sys.modules.pop(module_name, None)
    finally:
        if salvo_polars is not None:
            sys.modules["polars"] = salvo_polars
        else:
            sys.modules.pop("polars", None)
        for module_name in MODULES:
            sys.modules.pop(module_name, None)
        for module_name in MODULES:
            importlib.import_module(module_name)
