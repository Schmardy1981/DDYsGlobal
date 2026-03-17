###############################################################################
# Variables - DDYs Global Compliance Platform
###############################################################################

# --- Project ---
variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "region" {
  description = "GCP region - MUST be europe-west6 for Swiss data residency"
  type        = string
  default     = "europe-west6"

  validation {
    condition     = var.region == "europe-west6"
    error_message = "Region must be europe-west6 (Zurich) for FINMA/Swiss data residency compliance."
  }
}

variable "zone" {
  description = "Primary GCP zone"
  type        = string
  default     = "europe-west6-a"
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be dev, staging, or prod."
  }
}

# --- Networking ---
variable "vpc_cidr_primary" {
  description = "Primary subnet CIDR range"
  type        = string
  default     = "10.10.0.0/20"
}

variable "vpc_cidr_serverless" {
  description = "Serverless VPC connector CIDR range"
  type        = string
  default     = "10.8.0.0/28"
}

# --- Domain ---
variable "domain_name" {
  description = "Primary domain for the platform (e.g., compliance.ddys.ch)"
  type        = string
  default     = ""
}

variable "api_subdomain" {
  description = "API subdomain prefix"
  type        = string
  default     = "api"
}

# --- Cloud Run Backend ---
variable "backend_image" {
  description = "Full image path for backend container"
  type        = string
  default     = ""
}

variable "backend_cpu" {
  description = "CPU allocation for backend (e.g., 1, 2, 4)"
  type        = string
  default     = "2"
}

variable "backend_memory" {
  description = "Memory allocation for backend (e.g., 512Mi, 1Gi, 2Gi)"
  type        = string
  default     = "1Gi"
}

variable "backend_min_instances" {
  description = "Minimum number of backend instances"
  type        = number
  default     = 1
}

variable "backend_max_instances" {
  description = "Maximum number of backend instances"
  type        = number
  default     = 10
}

variable "backend_concurrency" {
  description = "Max concurrent requests per backend instance"
  type        = number
  default     = 80
}

variable "backend_timeout" {
  description = "Request timeout in seconds"
  type        = number
  default     = 300
}

# --- Cloud Run Frontend ---
variable "frontend_image" {
  description = "Full image path for frontend container"
  type        = string
  default     = ""
}

variable "frontend_cpu" {
  description = "CPU allocation for frontend"
  type        = string
  default     = "1"
}

variable "frontend_memory" {
  description = "Memory allocation for frontend"
  type        = string
  default     = "512Mi"
}

variable "frontend_min_instances" {
  description = "Minimum number of frontend instances"
  type        = number
  default     = 1
}

variable "frontend_max_instances" {
  description = "Maximum number of frontend instances"
  type        = number
  default     = 5
}

# --- MongoDB Atlas ---
variable "mongodb_atlas_org_id" {
  description = "MongoDB Atlas Organization ID"
  type        = string
  default     = ""
}

variable "mongodb_atlas_project_name" {
  description = "MongoDB Atlas Project Name"
  type        = string
  default     = "ddys-compliance"
}

variable "mongodb_cluster_tier" {
  description = "MongoDB Atlas cluster tier (M10, M20, M30, etc.)"
  type        = string
  default     = "M10"
}

variable "mongodb_version" {
  description = "MongoDB version"
  type        = string
  default     = "7.0"
}

# --- Storage ---
variable "document_retention_days" {
  description = "Document retention period in days for compliance"
  type        = number
  default     = 3650 # 10 years for FINMA compliance
}

variable "initial_tenant_ids" {
  description = "Initial tenant IDs for bucket creation"
  type        = list(string)
  default     = []
}

# --- Cloud Armor / Security ---
variable "cloud_armor_enabled" {
  description = "Enable Cloud Armor WAF policies"
  type        = bool
  default     = true
}

variable "rate_limit_threshold" {
  description = "Rate limit: max requests per minute per IP"
  type        = number
  default     = 300
}

# --- Alerting ---
variable "alert_email" {
  description = "Email address for monitoring alerts"
  type        = string
  default     = ""
}

variable "alert_slack_webhook" {
  description = "Slack webhook URL for alerts (optional)"
  type        = string
  default     = ""
  sensitive   = true
}

# --- Cloud Build ---
variable "github_owner" {
  description = "GitHub repository owner"
  type        = string
  default     = ""
}

variable "github_repo" {
  description = "GitHub repository name"
  type        = string
  default     = "DDYsGlobal"
}

variable "github_branch" {
  description = "Branch to trigger builds from"
  type        = string
  default     = "main"
}

# --- Cost Control ---
variable "budget_amount" {
  description = "Monthly budget alert threshold in CHF"
  type        = number
  default     = 500
}
