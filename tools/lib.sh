#!/usr/bin/env bash

project_node_version() {
  local root_dir="$1"
  if [[ -n "${NODENV_VERSION:-}" ]]; then
    printf '%s\n' "$NODENV_VERSION"
    return 0
  fi

  local version_file="$root_dir/.node-version"
  if [[ ! -r "$version_file" ]]; then
    printf '.node-version not found or not readable: %s\n' "$version_file" >&2
    return 2
  fi

  tr -d '[:space:]' < "$version_file"
  printf '\n'
}

load_env_file() {
  local env_file="$1"
  if [[ ! -f "$env_file" ]]; then
    return 0
  fi

  set -a
  # shellcheck disable=SC1090
  source "$env_file"
  set +a
}

print_operation_summary() {
  local title="$1"
  local target="$2"
  local changes="$3"
  local unchanged="$4"
  local smoke="$5"

  cat <<SUMMARY
[$title] Operation summary
  Target: $target
  Changes: $changes
  Unchanged: $unchanged
  Smoke checks: $smoke
SUMMARY
}
