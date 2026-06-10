variable "account_id" {
  description = "Cloudflare account ID."
  type        = string
}

variable "zone_id" {
  description = "Cloudflare zone ID for the app domain."
  type        = string
}

variable "zone_name" {
  description = "Cloudflare zone name, for example example.com."
  type        = string
}

variable "project_name" {
  description = "Cloudflare Pages project name."
  type        = string
  default     = "vocaloid-title-search"
}

variable "worker_script_base_name" {
  description = "Base Worker script name used by wrangler.toml."
  type        = string
  default     = "vocaloid-title-search-api"
}

variable "production_branch" {
  description = "Pages production branch name."
  type        = string
  default     = "production"
}

variable "production_hostname" {
  description = "Production custom hostname."
  type        = string
}

variable "staging_hostname" {
  description = "Staging custom hostname."
  type        = string
}

variable "d1_database_names" {
  description = "D1 database names for each environment."
  type = object({
    dev        = string
    staging    = string
    production = string
  })
  default = {
    dev        = "vocaloid-title-search-dev"
    staging    = "vocaloid-title-search-staging"
    production = "vocaloid-title-search-prod"
  }
}

variable "worker_script_names" {
  description = "Deployed Worker script names for custom routes."
  type = object({
    staging    = string
    production = string
  })
  default = {
    staging    = "vocaloid-title-search-api-staging"
    production = "vocaloid-title-search-api-production"
  }
}

variable "manage_worker_routes" {
  description = "Set false during first bootstrap if Worker scripts do not exist yet."
  type        = bool
  default     = true
}
