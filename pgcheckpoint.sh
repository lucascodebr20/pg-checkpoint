#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

if command -v python3 &>/dev/null; then
    python3 "$SCRIPT_DIR/pgcheckpoint.py"
elif command -v python &>/dev/null; then
    python "$SCRIPT_DIR/pgcheckpoint.py"
else
    echo ""
    echo "[ERRO] Python nao encontrado."
    echo "Instale com:"
    echo "  macOS:  brew install python"
    echo "  Linux:  sudo apt install python3  (ou equivalente)"
    echo ""
    exit 1
fi
