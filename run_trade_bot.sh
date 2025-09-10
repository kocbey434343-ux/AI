#!/usr/bin/env bash
# Cross-platform launcher (Linux/macOS). For Windows use run_trade_bot.ps1 (future).
# CR-0032 launcher script: activates venv, runs trade bot with symbol list and optional offline mode.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"
VENV_DIR="${PROJECT_ROOT}/.venv"
PYTHON_BIN="${VENV_DIR}/Scripts/python"
if [ ! -x "$PYTHON_BIN" ]; then
  PYTHON_BIN="${VENV_DIR}/bin/python"
fi
if [ ! -x "$PYTHON_BIN" ]; then
  echo "Python venv bulunamadi (.venv). Once sanal ortami olusturun." >&2
  exit 1
fi
SYMBOLS=${1:-"BTCUSDT"}
export RUN_SYMBOLS="$SYMBOLS"
export OFFLINE_MODE=${OFFLINE_MODE:-auto}
exec "$PYTHON_BIN" -m src.main "$@"
