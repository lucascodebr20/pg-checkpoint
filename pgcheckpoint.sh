#!/usr/bin/env bash
# Use: ./pgcheckpoint.sh        -> abre a interface grafica
#      ./pgcheckpoint.sh --cli  -> abre o menu no terminal
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

if command -v python3 &>/dev/null; then
    python3 -m pgcheckpoint "$@"
elif command -v python &>/dev/null; then
    python -m pgcheckpoint "$@"
else
    echo ""
    echo "[ERRO] Python nao encontrado."
    echo "Instale com:"
    echo "  macOS:  brew install python"
    echo "  Linux:  sudo apt install python3  (ou equivalente)"
    echo ""
    exit 1
fi
