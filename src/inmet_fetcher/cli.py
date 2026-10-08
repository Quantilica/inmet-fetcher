"""Standalone command-line interface for inmet-fetcher."""

from __future__ import annotations

import sys

_HOST_MODULES = {"typer", "rich", "quantilica"}

try:
    from .plugin import app
except ImportError as exc:  # host (typer/rich/quantilica-cli) ausente
    if (exc.name or "").split(".")[0] not in _HOST_MODULES:
        raise
    app = None
    _PLUGIN_ERROR = exc
else:
    _PLUGIN_ERROR = None


def main(argv: list[str] | None = None) -> None:
    """Run the standalone CLI for inmet-fetcher.

    Args:
        argv: Optional list of command-line arguments to parse. Defaults to sys.argv.

    Raises:
        SystemExit: Always — 0 on success (via Typer), 1 when the host
            (typer/rich/quantilica-cli) is not installed.
    """
    if app is None:
        print(
            "Erro: CLI requer 'typer' e 'rich' (via quantilica-cli). "
            'Instale via "quantilica install inmet". '
            f"Detalhe: {_PLUGIN_ERROR}",
            file=sys.stderr,
        )
        raise SystemExit(1)
    if argv is not None:
        sys.argv = [sys.argv[0]] + argv
    try:
        app()
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    main()
