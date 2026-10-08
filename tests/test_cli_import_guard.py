"""Import guard da CLI standalone e do pacote sem o extra ``analysis``."""

from __future__ import annotations

import importlib
import sys
import types

import pytest

import inmet_fetcher.cli as cli_module

_PLUGIN_KEY = "inmet_fetcher.plugin"
_PKG = "inmet_fetcher"


def _pkg_modules() -> dict[str, object]:
    """Snapshot dos módulos do pacote presentes em sys.modules."""
    return {
        name: mod
        for name, mod in sys.modules.items()
        if name == _PKG or name.startswith(_PKG + ".")
    }


@pytest.fixture
def _no_plugin():
    """Simular host ausente (typer e quantilica.cli.sdk bloqueados).

    O plugin do inmet importa o host via ``quantilica.cli.sdk`` (sem ``import
    typer`` direto); bloquear só ``typer`` não quebraria o reimport porque o
    SDK já está em ``sys.modules``. Restaura os módulos ao final.
    """
    saved_host = {key: sys.modules.get(key) for key in ("typer", "quantilica.cli.sdk")}
    had_plugin = _PLUGIN_KEY in sys.modules
    saved_plugin = sys.modules.get(_PLUGIN_KEY)
    saved_pkg = _pkg_modules()
    sys.modules["typer"] = None
    sys.modules["quantilica.cli.sdk"] = None
    sys.modules.pop(_PLUGIN_KEY, None)  # forcar reimport do plugin
    mod = importlib.reload(cli_module)
    yield mod
    for key, saved in saved_host.items():
        if saved is None:
            sys.modules.pop(key, None)
        else:
            sys.modules[key] = saved
    if had_plugin:
        sys.modules[_PLUGIN_KEY] = saved_plugin
    elif _PLUGIN_KEY in sys.modules:
        del sys.modules[_PLUGIN_KEY]
    importlib.reload(cli_module)
    sys.modules.update(saved_pkg)
    if _PKG in saved_pkg:
        importlib.reload(sys.modules[_PKG])


@pytest.fixture
def _no_analysis():
    """Bloquear ``polars``/``quantilica.analytics`` e restaurar os módulos ao final."""
    blocked = ["polars", "quantilica.analytics"]
    saved_blocked = {key: sys.modules.get(key) for key in blocked}
    saved_pkg = _pkg_modules()
    for key in blocked:
        sys.modules[key] = None
    for name in [n for n in sys.modules if n == _PKG or n.startswith(_PKG + ".")]:
        del sys.modules[name]
    mod = importlib.import_module(_PKG)
    yield mod
    for key, saved in saved_blocked.items():
        if saved is None:
            sys.modules.pop(key, None)
        else:
            sys.modules[key] = saved
    sys.modules.update(saved_pkg)
    if _PKG in saved_pkg:
        importlib.reload(sys.modules[_PKG])


def test_import_cli_sem_plugin_nao_levanta_erro(_no_plugin) -> None:
    """Importar cli sem o plugin disponível não levanta ModuleNotFoundError."""
    assert _no_plugin.app is None
    assert _no_plugin._PLUGIN_ERROR is not None


def test_main_sem_plugin_sai_1_e_orienta_install(_no_plugin, capsys) -> None:
    """main() sai com SystemExit(1) e mensagem com 'quantilica install inmet'."""
    with pytest.raises(SystemExit) as exc_info:
        _no_plugin.main([])
    assert exc_info.value.code == 1
    stderr = capsys.readouterr().err
    assert "Erro: CLI requer 'typer' e 'rich' (via quantilica-cli)." in stderr
    assert 'Instale via "quantilica install inmet".' in stderr
    assert "Detalhe:" in stderr


def test_importerror_interno_do_plugin_propaga() -> None:
    """ImportError de modulo fora do host (bug interno) nao vira exit 1: propaga."""
    saved = sys.modules.get(_PLUGIN_KEY)
    stub = types.ModuleType(_PLUGIN_KEY)

    def __getattr__(name):
        raise ModuleNotFoundError("No module named 'outro_modulo'", name="outro_modulo")

    stub.__getattr__ = __getattr__
    sys.modules[_PLUGIN_KEY] = stub
    try:
        with pytest.raises(ModuleNotFoundError):
            importlib.reload(cli_module)
    finally:
        if saved is None:
            sys.modules.pop(_PLUGIN_KEY, None)
        else:
            sys.modules[_PLUGIN_KEY] = saved
        importlib.reload(cli_module)


def test_import_inmet_sem_polars(_no_analysis) -> None:
    """import inmet_fetcher funciona sem polars/analysis (extra opcional)."""
    import inmet_fetcher

    assert inmet_fetcher._HAS_ANALYSIS is False
    assert inmet_fetcher.read is None
    assert inmet_fetcher.read_stations is None
    assert inmet_fetcher.BDMEP_CONTRACT is None
    assert inmet_fetcher.write_to_parquet is None
