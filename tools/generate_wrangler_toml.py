#!/usr/bin/env python3
"""Generate cloudflare/worker/wrangler.toml from local Terraform state."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_STATE_PATH = ROOT_DIR / "infra" / "cloudflare" / "terraform.tfstate"
DEFAULT_TEMPLATE_PATH = ROOT_DIR / "cloudflare" / "worker" / "wrangler.toml.example"
DEFAULT_OUTPUT_PATH = ROOT_DIR / "cloudflare" / "worker" / "wrangler.toml"
DEFAULT_DEV_CORS = "http://127.0.0.1:5173"


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate ignored wrangler.toml from Terraform state.",
    )
    parser.add_argument(
        "--state",
        type=Path,
        default=DEFAULT_STATE_PATH,
        help="Terraform state path. Default: infra/cloudflare/terraform.tfstate",
    )
    parser.add_argument(
        "--template",
        type=Path,
        default=DEFAULT_TEMPLATE_PATH,
        help="Template wrangler.toml path. Default: cloudflare/worker/wrangler.toml.example",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="Output wrangler.toml path. Default: cloudflare/worker/wrangler.toml",
    )
    parser.add_argument(
        "--dev-cors",
        default=DEFAULT_DEV_CORS,
        help=f"Local dev CORS origin. Default: {DEFAULT_DEV_CORS}",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print generated TOML without writing it.",
    )
    return parser.parse_args(argv)


def load_json(path: Path) -> dict[str, Any]:
    try:
        with path.open(encoding="utf-8") as file:
            return json.load(file)
    except FileNotFoundError:
        raise SystemExit(f"Terraform state not found: {path}") from None
    except json.JSONDecodeError as error:
        raise SystemExit(f"Invalid Terraform state JSON: {path}: {error}") from None


def load_template_values(path: Path) -> dict[str, str]:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise SystemExit(f"Template not found: {path}") from None

    values: dict[str, str] = {}
    for key in ("name", "main", "compatibility_date"):
        match = re.search(rf'(?m)^{re.escape(key)}\s*=\s*"([^"]+)"\s*$', text)
        if match:
            values[key] = match.group(1)

    missing = [key for key in ("name", "main", "compatibility_date") if key not in values]
    if missing:
        raise SystemExit(f"Template missing required keys: {', '.join(missing)}")
    return values


def output_value(state: dict[str, Any], name: str) -> Any:
    output = state.get("outputs", {}).get(name)
    if not isinstance(output, dict) or "value" not in output:
        return None
    return output["value"]


def resource_instances(state: dict[str, Any], resource_type: str) -> list[dict[str, Any]]:
    instances: list[dict[str, Any]] = []
    for resource in state.get("resources", []):
        if resource.get("type") != resource_type:
            continue
        for instance in resource.get("instances", []):
            values = dict(instance.get("attributes", {}))
            values["_resource_name"] = resource.get("name")
            values["_index_key"] = instance.get("index_key")
            instances.append(values)
    return instances


def collect_d1_databases(state: dict[str, Any]) -> dict[str, dict[str, str]]:
    ids = output_value(state, "d1_database_ids") or {}
    databases: dict[str, dict[str, str]] = {}

    for instance in resource_instances(state, "cloudflare_d1_database"):
        env = str(instance.get("_resource_name") or "")
        if env not in {"dev", "staging", "production"}:
            continue
        database_id = str(instance.get("id") or ids.get(env) or "")
        database_name = str(instance.get("name") or "")
        if database_id and database_name:
            databases[env] = {"id": database_id, "name": database_name}

    for env, database_id in ids.items():
        if env not in databases and database_id:
            databases[str(env)] = {"id": str(database_id), "name": f"vocaloid-title-search-{env}"}

    missing = [env for env in ("dev", "staging", "production") if env not in databases]
    if missing:
        raise SystemExit(f"Terraform state missing D1 database data for: {', '.join(missing)}")
    return databases


def collect_domains(state: dict[str, Any]) -> dict[str, str]:
    domains = output_value(state, "pages_custom_domains") or {}
    if isinstance(domains, dict):
        collected = {str(key): str(value) for key, value in domains.items() if value}
    else:
        collected = {}

    for instance in resource_instances(state, "cloudflare_pages_domain"):
        env = str(instance.get("_index_key") or "")
        domain = str(instance.get("name") or instance.get("id") or "")
        if env in {"staging", "production"} and domain:
            collected[env] = domain

    missing = [env for env in ("staging", "production") if env not in collected]
    if missing:
        raise SystemExit(f"Terraform state missing Pages custom domain data for: {', '.join(missing)}")
    return collected


def toml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def render_wrangler_toml(
    template_values: dict[str, str],
    databases: dict[str, dict[str, str]],
    domains: dict[str, str],
    dev_cors: str,
) -> str:
    staging_origin = f"https://{domains['staging']}"
    production_origin = f"https://{domains['production']}"
    lines = [
        "# Generated by tools/generate_wrangler_toml.py.",
        "# Do not commit this file. Worker routes, DNS, Pages domains, and D1 resources are managed by Terraform.",
        f"name = {toml_string(template_values['name'])}",
        f"main = {toml_string(template_values['main'])}",
        f"compatibility_date = {toml_string(template_values['compatibility_date'])}",
        "",
        "[vars]",
        f"CORS_ORIGINS = {toml_string(dev_cors)}",
        "",
        "[[d1_databases]]",
        'binding = "DB"',
        f"database_name = {toml_string(databases['dev']['name'])}",
        f"database_id = {toml_string(databases['dev']['id'])}",
        "",
        "[env.staging]",
        "# Worker routes are managed by Terraform in infra/cloudflare.",
        "",
        "[env.staging.vars]",
        f"CORS_ORIGINS = {toml_string(staging_origin)}",
        "",
        "[[env.staging.d1_databases]]",
        'binding = "DB"',
        f"database_name = {toml_string(databases['staging']['name'])}",
        f"database_id = {toml_string(databases['staging']['id'])}",
        "",
        "[env.production]",
        "# Worker routes are managed by Terraform in infra/cloudflare.",
        "",
        "[env.production.vars]",
        f"CORS_ORIGINS = {toml_string(production_origin)}",
        "",
        "[[env.production.d1_databases]]",
        'binding = "DB"',
        f"database_name = {toml_string(databases['production']['name'])}",
        f"database_id = {toml_string(databases['production']['id'])}",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    state = load_json(args.state)
    template_values = load_template_values(args.template)
    databases = collect_d1_databases(state)
    domains = collect_domains(state)
    rendered = render_wrangler_toml(template_values, databases, domains, args.dev_cors)

    if args.dry_run:
        print(rendered, end="")
        return 0

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")
    print(f"Generated {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
