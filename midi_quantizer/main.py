"""Punto de entrada de MIDI Quantizer Pro.

Sin argumentos abre la GUI; con argumentos ejecuta el CLI.
"""

from __future__ import annotations

import sys


def main() -> int:
    """Decide entre GUI y CLI según los argumentos recibidos."""
    if len(sys.argv) > 1:
        from .cli import main as cli_main

        return cli_main(sys.argv[1:])

    try:
        from .gui import run
    except ImportError as exc:
        print(f"No se pudo iniciar la GUI (¿falta tkinter?): {exc}", file=sys.stderr)
        return 1
    run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
