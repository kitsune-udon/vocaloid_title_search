#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT_DIR/tools/lib.sh"
DB_PATH="${VOCALOID_DB_PATH:-$ROOT_DIR/vocaloid_titles.sqlite3}"
SQL_OUTPUT="${VOCALOID_D1_SQL_OUTPUT:-}"
BACKUP_DIR="${VOCALOID_D1_BACKUP_DIR:-}"
D1_DATABASE="${VOCALOID_D1_DATABASE:-}"
PUBLIC_BASE_URL="${VOCALOID_PUBLIC_BASE_URL:-}"
WORKER_DIR="${VOCALOID_WORKER_DIR:-$ROOT_DIR/cloudflare/worker}"
NODE_VERSION="$(project_node_version "$ROOT_DIR")"
TARGET_ENV="${VOCALOID_DEPLOY_ENV:-}"
ENV_FILE="${VOCALOID_ENV_FILE:-$ROOT_DIR/.env}"
DRY_RUN=0
ASSUME_YES=0
SKIP_SMOKE_CHECKS=0
SKIP_SMOKE_CHECKS_EXPLICIT=0
BACKUP_PATH=""
ROLLBACK_SQL=""

usage() {
  cat <<'USAGE'
Usage:
  tools/update_d1.sh --env staging
  tools/update_d1.sh --env production

Options:
  --env ENV                  Target environment: staging or production. Required.
  --base-url URL             Public site URL used for post-update smoke checks.
  --db-path PATH             SQLite DB path. Default: vocaloid_titles.sqlite3
  --sql-output PATH          D1 SQL output path. Default: release/d1/<env>/vocaloid_titles.sql
  --database NAME            D1 database name. Default: vocaloid-title-search-staging or vocaloid-title-search-prod
  --backup-dir PATH          Backup directory. Default: release/backups/<env>
  --skip-smoke-checks        Do not run post-update public API checks.
  --dry-run                  Print commands without changing DB or D1.
  --yes                      Do not prompt before remote D1 update.
  -h, --help                 Show this help.

Environment:
  VOCALOID_PUBLIC_BASE_URL, VOCALOID_DB_PATH, VOCALOID_D1_SQL_OUTPUT,
  VOCALOID_D1_DATABASE, VOCALOID_D1_BACKUP_DIR, VOCALOID_WORKER_DIR,
  VOCALOID_DEPLOY_ENV, VOCALOID_ENV_FILE, NODENV_VERSION
USAGE
}

log() {
  printf '[update-d1] %s\n' "$*"
}

run() {
  if [[ "$DRY_RUN" -eq 1 ]]; then
    printf '+'
    printf ' %q' "$@"
    printf '\n'
    return 0
  fi
  "$@"
}

run_in_worker_dir() {
  if [[ "$DRY_RUN" -eq 1 ]]; then
    printf '+ cd %q &&' "$WORKER_DIR"
    printf ' %q' "$@"
    printf '\n'
    return 0
  fi
  (cd "$WORKER_DIR" && "$@")
}

elapsed_seconds() {
  local started_at="$1"
  echo "$(( $(date +%s) - started_at ))"
}

resolve_d1_database_name() {
  local env_name="$1"
  local state_path="$ROOT_DIR/infra/cloudflare/terraform.tfstate"
  if [[ ! -f "$state_path" ]]; then
    return 1
  fi
  python3 - "$state_path" "$env_name" <<'PY'
import json
import sys

state_path, env_name = sys.argv[1], sys.argv[2]
try:
    with open(state_path, encoding="utf-8") as file:
        state = json.load(file)
except (OSError, json.JSONDecodeError):
    raise SystemExit(1)

for resource in state.get("resources", []):
    if resource.get("type") != "cloudflare_d1_database" or resource.get("name") != env_name:
        continue
    for instance in resource.get("instances", []):
        name = instance.get("attributes", {}).get("name")
        if name:
            print(name)
            raise SystemExit(0)
raise SystemExit(1)
PY
}

resolve_public_base_url() {
  local env_name="$1"
  local state_path="$ROOT_DIR/infra/cloudflare/terraform.tfstate"
  if [[ ! -f "$state_path" ]]; then
    return 1
  fi
  python3 - "$state_path" "$env_name" <<'PY'
import json
import sys

state_path, env_name = sys.argv[1], sys.argv[2]
try:
    with open(state_path, encoding="utf-8") as file:
        state = json.load(file)
except (OSError, json.JSONDecodeError):
    raise SystemExit(1)

output = state.get("outputs", {}).get("pages_custom_domains", {}).get("value", {})
if isinstance(output, dict) and output.get(env_name):
    print(f"https://{output[env_name]}")
    raise SystemExit(0)

for resource in state.get("resources", []):
    if resource.get("type") != "cloudflare_pages_domain":
        continue
    for instance in resource.get("instances", []):
        if instance.get("index_key") != env_name:
            continue
        name = instance.get("attributes", {}).get("name")
        if name:
            print(f"https://{name}")
            raise SystemExit(0)
raise SystemExit(1)
PY
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --env)
      TARGET_ENV="${2:?--env requires a value}"
      shift 2
      ;;
    --base-url)
      PUBLIC_BASE_URL="${2:?--base-url requires a value}"
      shift 2
      ;;
    --db-path)
      DB_PATH="${2:?--db-path requires a value}"
      shift 2
      ;;
    --sql-output)
      SQL_OUTPUT="${2:?--sql-output requires a value}"
      shift 2
      ;;
    --database)
      D1_DATABASE="${2:?--database requires a value}"
      shift 2
      ;;
    --backup-dir)
      BACKUP_DIR="${2:?--backup-dir requires a value}"
      shift 2
      ;;
    --skip-smoke-checks)
      SKIP_SMOKE_CHECKS=1
      SKIP_SMOKE_CHECKS_EXPLICIT=1
      shift
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --yes)
      ASSUME_YES=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      printf 'Unknown option: %s\n\n' "$1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

load_env_file "$ENV_FILE"

case "$TARGET_ENV" in
  staging|production) ;;
  "")
    printf 'TARGET_ENV is required. Pass --env staging or --env production.\n' >&2
    exit 2
    ;;
  *)
    printf 'Unsupported TARGET_ENV: %s. Use staging or production.\n' "$TARGET_ENV" >&2
    exit 2
    ;;
esac

if [[ -z "$D1_DATABASE" ]]; then
  if ! D1_DATABASE="$(resolve_d1_database_name "$TARGET_ENV")"; then
    case "$TARGET_ENV" in
      staging) D1_DATABASE="vocaloid-title-search-staging" ;;
      production) D1_DATABASE="vocaloid-title-search-prod" ;;
    esac
  fi
fi

if [[ -z "$PUBLIC_BASE_URL" && "$SKIP_SMOKE_CHECKS_EXPLICIT" -eq 0 ]]; then
  if PUBLIC_BASE_URL="$(resolve_public_base_url "$TARGET_ENV")"; then
    SKIP_SMOKE_CHECKS=0
  fi
fi

if [[ -z "$SQL_OUTPUT" ]]; then
  SQL_OUTPUT="$ROOT_DIR/release/d1/$TARGET_ENV/vocaloid_titles.sql"
fi

if [[ -z "$BACKUP_DIR" ]]; then
  BACKUP_DIR="$ROOT_DIR/release/backups/$TARGET_ENV"
fi

if [[ -n "$PUBLIC_BASE_URL" ]]; then
  case "$PUBLIC_BASE_URL" in
    http://*|https://*) ;;
    *)
      printf 'PUBLIC_BASE_URL must start with http:// or https://\n' >&2
      exit 2
      ;;
  esac
else
  SKIP_SMOKE_CHECKS=1
fi

if [[ ! -d "$WORKER_DIR" ]]; then
  printf 'Worker directory not found: %s\n' "$WORKER_DIR" >&2
  exit 2
fi

if [[ ! -f "$DB_PATH" ]]; then
  printf 'SQLite DB not found: %s\n' "$DB_PATH" >&2
  printf 'Build it first, for example:\n\n' >&2
  printf '  uv run --cache-dir .uv-cache python -m vocaloid_title_search.cli.build_db --db-path %q\n\n' "$DB_PATH" >&2
  exit 2
fi

STARTED_AT="$(date +%s)"
log "Environment: $TARGET_ENV"
log "DB path: $DB_PATH"
log "D1 SQL: $SQL_OUTPUT"
log "Backup dir: $BACKUP_DIR"
log "D1 database: $D1_DATABASE"
if [[ "$SKIP_SMOKE_CHECKS" -eq 1 ]]; then
  log "Public URL: - (smoke checks skipped)"
else
  log "Public URL: $PUBLIC_BASE_URL"
fi
if [[ "$SKIP_SMOKE_CHECKS" -eq 1 ]]; then
  UPDATE_SMOKE_TEXT="skipped"
else
  UPDATE_SMOKE_TEXT="$PUBLIC_BASE_URL"
fi
print_operation_summary \
  "update-d1" \
  "$TARGET_ENV" \
  "D1 data in $D1_DATABASE" \
  "SQLite source DB, Pages artifact, Worker script, Terraform resources" \
  "$UPDATE_SMOKE_TEXT"

log "Validating local SQLite DB"
run python3 -m vocaloid_title_search.cli.validate_db \
  --db-path "$DB_PATH"

if [[ "$DRY_RUN" -eq 0 ]]; then
  BACKUP_PATH="$BACKUP_DIR/$(date +%Y%m%d-%H%M%S)"
  mkdir -p "$BACKUP_PATH"
  if [[ -f "$DB_PATH" ]]; then
    cp -p "$DB_PATH" "$BACKUP_PATH/previous-vocaloid_titles.sqlite3"
  fi
  if [[ -f "$SQL_OUTPUT" ]]; then
    cp -p "$SQL_OUTPUT" "$BACKUP_PATH/previous-vocaloid_titles.sql"
    ROLLBACK_SQL="$BACKUP_PATH/previous-vocaloid_titles.sql"
  fi
  log "Prepared backup directory: $BACKUP_PATH"
fi

log "Exporting D1 SQL"
run python3 "$ROOT_DIR/tools/export_d1_sql.py" \
  --db-path "$DB_PATH" \
  --output "$SQL_OUTPUT"

if [[ "$DRY_RUN" -eq 0 ]]; then
  cp -p "$DB_PATH" "$BACKUP_PATH/new-vocaloid_titles.sqlite3"
  cp -p "$SQL_OUTPUT" "$BACKUP_PATH/new-vocaloid_titles.sql"
  if grep -Eiq '(^|[[:space:];])(BEGIN|COMMIT|SAVEPOINT)([[:space:];]|$)' "$SQL_OUTPUT"; then
    printf 'D1 SQL contains transaction statements. Refusing remote D1 load: %s\n' "$SQL_OUTPUT" >&2
    exit 1
  fi
fi

if [[ "$ASSUME_YES" -eq 0 && "$DRY_RUN" -eq 0 ]]; then
  printf 'This will replace remote %s D1 database "%s". Continue? [y/N] ' "$TARGET_ENV" "$D1_DATABASE"
  read -r answer
  case "$answer" in
    y|Y|yes|YES) ;;
    *)
      printf 'Aborted.\n' >&2
      exit 1
      ;;
  esac
fi

log "Loading SQL into remote D1"
run_in_worker_dir env NODENV_VERSION="$NODE_VERSION" ./node_modules/.bin/wrangler d1 execute "$D1_DATABASE" \
  --remote \
  --file "$SQL_OUTPUT"

if [[ "$SKIP_SMOKE_CHECKS" -eq 1 ]]; then
  log "Skipping smoke checks"
else
  log "Running $TARGET_ENV smoke checks"
  if ! run python3 "$ROOT_DIR/tools/check_worker_api.py" --base-url "$PUBLIC_BASE_URL"; then
    if [[ -n "$ROLLBACK_SQL" ]]; then
      cat >&2 <<ROLLBACK
Smoke check failed. To roll back the D1 database to the saved backup, run:

  cd "$WORKER_DIR"
  ./node_modules/.bin/wrangler d1 execute "$D1_DATABASE" \\
    --remote \\
    --file "$ROLLBACK_SQL"

ROLLBACK
    else
      printf 'Smoke check failed. No previous D1 SQL backup was available for rollback.\n' >&2
    fi
    exit 1
  fi
fi

log "Done in $(elapsed_seconds "$STARTED_AT") seconds"
