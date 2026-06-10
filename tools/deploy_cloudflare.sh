#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT_DIR/tools/lib.sh"
WORKER_DIR="${VOCALOID_WORKER_DIR:-$ROOT_DIR/cloudflare/worker}"
FRONTEND_DIR="${VOCALOID_FRONTEND_DIR:-$ROOT_DIR/frontend}"
NODE_VERSION="$(project_node_version "$ROOT_DIR")"
PAGES_PROJECT="${VOCALOID_PAGES_PROJECT:-vocaloid-title-search}"
PUBLIC_BASE_URL="${VOCALOID_PUBLIC_BASE_URL:-}"
TARGET_ENV="${VOCALOID_DEPLOY_ENV:-}"
ENV_FILE="${VOCALOID_ENV_FILE:-$ROOT_DIR/.env}"
DRY_RUN=0
SKIP_BUILD=0
SKIP_PAGES=0
SKIP_WORKER=0
SKIP_SMOKE_CHECKS=0
SKIP_SMOKE_CHECKS_EXPLICIT=0
SKIP_WRANGLER_TOML=0
ASSUME_YES=0

usage() {
  cat <<'USAGE'
Usage:
  tools/deploy_cloudflare.sh --env staging
  tools/deploy_cloudflare.sh --env production

Options:
  --env ENV          Target environment: staging or production. Required.
  --base-url URL     Public site URL used for post-deploy smoke checks.
  --project NAME     Cloudflare Pages project name. Default: vocaloid-title-search
  --skip-build       Reuse existing frontend/dist.
  --skip-pages       Do not deploy Cloudflare Pages.
  --skip-worker      Do not deploy Cloudflare Worker.
  --skip-smoke-checks
                    Do not run post-deploy public API checks.
  --skip-wrangler-toml
                      Do not regenerate cloudflare/worker/wrangler.toml.
  --dry-run          Print commands without deploying.
  --yes              Do not prompt before production deploy.
  -h, --help         Show this help.

Environment:
  VOCALOID_DEPLOY_ENV, VOCALOID_PAGES_PROJECT, VOCALOID_WORKER_DIR,
  VOCALOID_FRONTEND_DIR, VOCALOID_PUBLIC_BASE_URL, VOCALOID_ENV_FILE,
  NODENV_VERSION
USAGE
}

log() {
  printf '[deploy-cloudflare] %s\n' "$*"
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

run_in() {
  local directory="$1"
  shift
  if [[ "$DRY_RUN" -eq 1 ]]; then
    printf '+ cd %q &&' "$directory"
    printf ' %q' "$@"
    printf '\n'
    return 0
  fi
  (cd "$directory" && "$@")
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
    --project)
      PAGES_PROJECT="${2:?--project requires a value}"
      shift 2
      ;;
    --skip-build)
      SKIP_BUILD=1
      shift
      ;;
    --skip-pages)
      SKIP_PAGES=1
      shift
      ;;
    --skip-worker)
      SKIP_WORKER=1
      shift
      ;;
    --skip-smoke-checks)
      SKIP_SMOKE_CHECKS=1
      SKIP_SMOKE_CHECKS_EXPLICIT=1
      shift
      ;;
    --skip-wrangler-toml)
      SKIP_WRANGLER_TOML=1
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

load_env_file "$ENV_FILE"

if [[ -z "$PUBLIC_BASE_URL" && "$SKIP_SMOKE_CHECKS_EXPLICIT" -eq 0 ]]; then
  if PUBLIC_BASE_URL="$(resolve_public_base_url "$TARGET_ENV")"; then
    SKIP_SMOKE_CHECKS=0
  fi
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

if [[ ! -d "$FRONTEND_DIR" ]]; then
  printf 'Frontend directory not found: %s\n' "$FRONTEND_DIR" >&2
  exit 2
fi

if [[ ! -d "$WORKER_DIR" ]]; then
  printf 'Worker directory not found: %s\n' "$WORKER_DIR" >&2
  exit 2
fi

log "Environment: $TARGET_ENV"
log "Pages project: $PAGES_PROJECT"
if [[ "$SKIP_SMOKE_CHECKS" -eq 1 ]]; then
  log "Public URL: - (smoke checks skipped)"
else
  log "Public URL: $PUBLIC_BASE_URL"
fi

DEPLOY_CHANGES=()
if [[ "$SKIP_PAGES" -eq 0 ]]; then
  DEPLOY_CHANGES+=("Pages artifact")
fi
if [[ "$SKIP_WORKER" -eq 0 ]]; then
  DEPLOY_CHANGES+=("Worker script")
fi
if [[ "${#DEPLOY_CHANGES[@]}" -eq 0 ]]; then
  DEPLOY_CHANGES_TEXT="none"
else
  DEPLOY_CHANGES_TEXT=""
  for item in "${DEPLOY_CHANGES[@]}"; do
    if [[ -n "$DEPLOY_CHANGES_TEXT" ]]; then
      DEPLOY_CHANGES_TEXT+=", "
    fi
    DEPLOY_CHANGES_TEXT+="$item"
  done
fi
if [[ "$SKIP_SMOKE_CHECKS" -eq 1 ]]; then
  DEPLOY_SMOKE_TEXT="skipped"
else
  DEPLOY_SMOKE_TEXT="$PUBLIC_BASE_URL"
fi
print_operation_summary \
  "deploy-cloudflare" \
  "$TARGET_ENV" \
  "$DEPLOY_CHANGES_TEXT" \
  "D1 data, Terraform resources" \
  "$DEPLOY_SMOKE_TEXT"

if [[ "$TARGET_ENV" == "production" && "$ASSUME_YES" -eq 0 && "$DRY_RUN" -eq 0 && ( "$SKIP_PAGES" -eq 0 || "$SKIP_WORKER" -eq 0 ) ]]; then
  printf 'This will deploy Pages and/or Worker to production. Continue? [y/N] '
  read -r answer
  case "$answer" in
    y|Y|yes|YES) ;;
    *)
      printf 'Aborted.\n' >&2
      exit 1
      ;;
  esac
fi

if [[ "$SKIP_WORKER" -eq 0 ]]; then
  if [[ "$SKIP_WRANGLER_TOML" -eq 0 ]]; then
    if [[ -f "$ROOT_DIR/infra/cloudflare/terraform.tfstate" ]]; then
      log "Generating wrangler.toml from Terraform state"
      run python3 "$ROOT_DIR/tools/generate_wrangler_toml.py"
    elif [[ ! -f "$WORKER_DIR/wrangler.toml" ]]; then
      printf 'wrangler.toml is missing and Terraform state was not found.\n' >&2
      printf 'Create Terraform state first, or copy cloudflare/worker/wrangler.toml.example for bootstrap.\n' >&2
      exit 2
    else
      log "Using existing wrangler.toml (Terraform state not found)"
    fi
  else
    log "Skipping wrangler.toml generation"
  fi
fi

if [[ "$SKIP_BUILD" -eq 0 ]]; then
  log "Building frontend"
  run_in "$FRONTEND_DIR" env NODENV_VERSION="$NODE_VERSION" yarn build
else
  log "Skipping frontend build"
fi

if [[ "$SKIP_PAGES" -eq 0 ]]; then
  if [[ "$SKIP_BUILD" -eq 1 && ! -f "$FRONTEND_DIR/dist/index.html" ]]; then
    printf 'frontend/dist/index.html not found. Remove --skip-build or build the frontend first.\n' >&2
    exit 2
  fi
  log "Deploying Pages branch: $TARGET_ENV"
  run env NODENV_VERSION="$NODE_VERSION" "$WORKER_DIR/node_modules/.bin/wrangler" pages deploy "$FRONTEND_DIR/dist" \
    --project-name "$PAGES_PROJECT" \
    --branch "$TARGET_ENV"
else
  log "Skipping Pages deploy"
fi

if [[ "$SKIP_WORKER" -eq 0 ]]; then
  log "Deploying Worker env: $TARGET_ENV"
  run_in "$WORKER_DIR" env NODENV_VERSION="$NODE_VERSION" ./node_modules/.bin/wrangler deploy --env "$TARGET_ENV"
else
  log "Skipping Worker deploy"
fi

if [[ "$SKIP_SMOKE_CHECKS" -eq 1 ]]; then
  log "Skipping smoke checks"
else
  log "Running $TARGET_ENV smoke checks"
  run python3 "$ROOT_DIR/tools/check_worker_api.py" --base-url "$PUBLIC_BASE_URL"
fi

log "Done"
