#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT_DIR/tools/lib.sh"
TERRAFORM_DIR="${VOCALOID_TERRAFORM_DIR:-$ROOT_DIR/infra/cloudflare}"
ENV_FILE="${VOCALOID_ENV_FILE:-$ROOT_DIR/.env}"

usage() {
  cat <<'USAGE'
Usage:
  tools/cloudflare_iac.sh init
  tools/cloudflare_iac.sh plan
  tools/cloudflare_iac.sh apply
  tools/cloudflare_iac.sh output
  tools/cloudflare_iac.sh import <address> <id>
  tools/cloudflare_iac.sh verify-token

Runs terraform in infra/cloudflare.

Environment:
  CLOUDFLARE_API_TOKEN    Cloudflare credential read by the provider
  VOCALOID_ENV_FILE       Override .env path. Default: ./.env
  VOCALOID_TERRAFORM_DIR  Override Terraform directory
  VOCALOID_TERRAFORM_ALLOW_EMPTY_STATE_APPLY=1
                         Allow apply when no local Terraform state exists
USAGE
}

if [[ $# -eq 0 || "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if ! command -v terraform >/dev/null 2>&1; then
  if [[ "${1:-}" != "verify-token" ]]; then
    printf 'terraform is not installed. Install Terraform or OpenTofu, then retry.\n' >&2
    exit 127
  fi
fi

if [[ ! -d "$TERRAFORM_DIR" ]]; then
  printf 'Terraform directory not found: %s\n' "$TERRAFORM_DIR" >&2
  exit 2
fi

load_env_file "$ENV_FILE"

if [[ "$1" == "verify-token" ]]; then
  if [[ -z "${CLOUDFLARE_API_TOKEN:-}" ]]; then
    printf 'CLOUDFLARE_API_TOKEN is not set.\n' >&2
    exit 2
  fi
  exec curl -sS https://api.cloudflare.com/client/v4/user/tokens/verify \
    -H "Authorization: Bearer $CLOUDFLARE_API_TOKEN"
fi

cd "$TERRAFORM_DIR"

case "$1" in
  apply)
    if [[ ! -s terraform.tfstate && "${VOCALOID_TERRAFORM_ALLOW_EMPTY_STATE_APPLY:-}" != "1" ]]; then
      cat >&2 <<'ERROR'
Refusing to run terraform apply without an existing local terraform.tfstate.

This repository already has Cloudflare resources in production. Import the
existing Pages project, D1 databases, DNS records, Pages domains, and Worker
routes first. If this is a truly new Cloudflare environment, set:

  VOCALOID_TERRAFORM_ALLOW_EMPTY_STATE_APPLY=1

Then rerun the command.
ERROR
      exit 2
    fi
    ;;
esac

exec terraform "$@"
