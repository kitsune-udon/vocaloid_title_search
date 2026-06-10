locals {
  pages_targets = {
    staging    = "staging.${var.project_name}.pages.dev"
    production = "${var.project_name}.pages.dev"
  }

  hostnames = {
    staging    = var.staging_hostname
    production = var.production_hostname
  }
}

resource "cloudflare_pages_project" "app" {
  account_id        = var.account_id
  name              = var.project_name
  production_branch = var.production_branch

  lifecycle {
    prevent_destroy = true
  }
}

resource "cloudflare_pages_domain" "app" {
  for_each = local.hostnames

  account_id   = var.account_id
  project_name = cloudflare_pages_project.app.name
  name         = each.value

  depends_on = [cloudflare_dns_record.pages_cname]
}

resource "cloudflare_dns_record" "pages_cname" {
  for_each = local.hostnames

  zone_id = var.zone_id
  name    = each.value
  type    = "CNAME"
  content = local.pages_targets[each.key]
  proxied = true
  ttl     = 1
  comment = "Managed by Terraform for ${var.project_name} ${each.key}"

  depends_on = [cloudflare_pages_project.app]
}

resource "cloudflare_d1_database" "dev" {
  account_id = var.account_id
  name       = var.d1_database_names.dev

  lifecycle {
    prevent_destroy = true
  }
}

resource "cloudflare_d1_database" "staging" {
  account_id = var.account_id
  name       = var.d1_database_names.staging

  lifecycle {
    prevent_destroy = true
  }
}

resource "cloudflare_d1_database" "production" {
  account_id = var.account_id
  name       = var.d1_database_names.production

  lifecycle {
    prevent_destroy = true
  }
}

resource "cloudflare_workers_route" "api" {
  for_each = var.manage_worker_routes ? {
    staging_api        = { hostname = var.staging_hostname, pattern = "/api/*", script = var.worker_script_names.staging }
    staging_health     = { hostname = var.staging_hostname, pattern = "/health", script = var.worker_script_names.staging }
    production_api     = { hostname = var.production_hostname, pattern = "/api/*", script = var.worker_script_names.production }
    production_health  = { hostname = var.production_hostname, pattern = "/health", script = var.worker_script_names.production }
  } : {}

  zone_id     = var.zone_id
  pattern     = "${each.value.hostname}${each.value.pattern}"
  script      = each.value.script
}
