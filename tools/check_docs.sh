#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

run() {
  printf '\n[check-docs] %s\n' "$*"
  "$@"
}

run python3 "$ROOT_DIR/tools/check_sensitive_values.py"
run python3 "$ROOT_DIR/tools/check_docs.py"

printf '\n[check-docs] OK\n'
