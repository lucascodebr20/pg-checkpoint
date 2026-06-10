"""Entry point: `python -m pgcheckpoint` abre a GUI; `--cli` abre o menu de terminal."""

import argparse
import sys


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="pgcheckpoint",
        description="Salve e restaure snapshots de bancos PostgreSQL locais.",
    )
    parser.add_argument(
        "--cli",
        action="store_true",
        help="usa o menu interativo no terminal em vez da interface grafica",
    )
    args = parser.parse_args()

    if args.cli:
        from .ui import cli

        cli.run()
        return

    try:
        from .ui import gui
    except ImportError:
        message = (
            "Flet nao instalado. Rode 'pip install flet' para usar a "
            "interface grafica, ou use o modo terminal (--cli)."
        )
        if sys.stdout is None:
            # Rodando via pythonw (sem console): avisa em janela nativa
            import ctypes

            ctypes.windll.user32.MessageBoxW(
                0, message, "PostgreSQL Checkpoint Manager", 0x10
            )
            return

        print(f"\n  [AVISO] {message} Abrindo modo terminal...\n")
        from .ui import cli

        cli.run()
        return

    gui.run()


if __name__ == "__main__":
    main()
