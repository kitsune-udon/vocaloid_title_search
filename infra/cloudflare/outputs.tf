output "pages_project_name" {
  description = "Cloudflare Pages project name."
  value       = cloudflare_pages_project.app.name
}

output "pages_custom_domains" {
  description = "Configured Pages custom domains."
  value       = { for key, value in cloudflare_pages_domain.app : key => value.name }
}

output "dns_targets" {
  description = "Expected Pages CNAME targets."
  value       = local.pages_targets
}

output "d1_database_ids" {
  description = "D1 database IDs to copy into cloudflare/worker/wrangler.toml."
  value = {
    dev        = cloudflare_d1_database.dev.id
    staging    = cloudflare_d1_database.staging.id
    production = cloudflare_d1_database.production.id
  }
}

output "worker_routes" {
  description = "Worker route patterns managed by Terraform."
  value       = { for key, value in cloudflare_workers_route.api : key => value.pattern }
}
