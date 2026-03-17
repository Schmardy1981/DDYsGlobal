# DDYs Global - Production Environment (Swiss Compliance)
project_id  = "ddys-compliance-prod"
environment = "prod"
region      = "europe-west6"

# Production domain
domain_name   = "compliance.ddys.ch"
api_subdomain = "api"

# MongoDB Atlas
mongodb_atlas_org_id       = ""
mongodb_atlas_project_name = "ddys-compliance-prod"
mongodb_cluster_tier       = "M30"
mongodb_version            = "7.0"

# Production scaling
backend_cpu           = "2"
backend_memory        = "2Gi"
backend_min_instances = 2
backend_max_instances = 20
backend_concurrency   = 80
backend_timeout       = 300

frontend_cpu           = "1"
frontend_memory        = "512Mi"
frontend_min_instances = 2
frontend_max_instances = 10

# Full security
cloud_armor_enabled  = true
rate_limit_threshold = 300

# Alerting
alert_email = "ops@ddys.ch"

# CI/CD
github_owner  = "DDYsGlobal"
github_repo   = "DDYsGlobal"
github_branch = "main"

# Production tenants
initial_tenant_ids = []

# FINMA compliance: 10-year retention
document_retention_days = 3650

# Production budget
budget_amount = 1500
