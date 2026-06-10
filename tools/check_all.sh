#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT_DIR/tools/lib.sh"
NODE_VERSION="$(project_node_version "$ROOT_DIR")"

run() {
  printf '\n[check-all] %s\n' "$*"
  "$@"
}

section() {
  printf '\n[check-all] == %s ==\n' "$1"
}

run_in() {
  local directory="$1"
  shift
  printf '\n[check-all] (cd %s) %s\n' "$directory" "$*"
  (cd "$directory" && "$@")
}

section "Shell scripts"
run bash -n "$ROOT_DIR/tools/check_all.sh"
run bash -n "$ROOT_DIR/tools/cloudflare_iac.sh"
run bash -n "$ROOT_DIR/tools/deploy_cloudflare.sh"
run bash -n "$ROOT_DIR/tools/lib.sh"
run bash -n "$ROOT_DIR/tools/update_d1.sh"

section "Repository privacy"
run python3 "$ROOT_DIR/tools/check_sensitive_values.py"
run python3 "$ROOT_DIR/tools/check_docs.py"
run python3 "$ROOT_DIR/tools/check_frontend_accessibility.py"
run python3 "$ROOT_DIR/tools/check_frontend_metadata.py"
run python3 "$ROOT_DIR/tools/check_api_contract_sources.py"

section "Python build-time tooling"
run python3 -m py_compile \
  "$ROOT_DIR/tools/check_api_contract_sources.py" \
  "$ROOT_DIR/tools/check_docs.py" \
  "$ROOT_DIR/tools/check_frontend_accessibility.py" \
  "$ROOT_DIR/tools/check_frontend_metadata.py" \
  "$ROOT_DIR/tools/check_sensitive_values.py" \
  "$ROOT_DIR/tools/check_worker_api.py" \
  "$ROOT_DIR/tools/export_d1_sql.py" \
  "$ROOT_DIR/tools/generate_wrangler_toml.py" \
  "$ROOT_DIR/tools/profile_worker_api.py"
run env PYTHONDONTWRITEBYTECODE=1 uv run --cache-dir "$ROOT_DIR/.uv-cache" python -m unittest

section "Cloudflare Worker API"
run_in "$ROOT_DIR/cloudflare/worker" env NODENV_VERSION="$NODE_VERSION" yarn typecheck
run_in "$ROOT_DIR/cloudflare/worker" env NODENV_VERSION="$NODE_VERSION" yarn test

section "Vue frontend"
run_in "$ROOT_DIR/frontend" env NODENV_VERSION="$NODE_VERSION" yarn build

printf '\n[check-all] OK\n'
