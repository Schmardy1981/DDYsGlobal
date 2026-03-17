# DDYs Global - Staging Environment
project_id  = "ddys-compliance-staging"
environment = "staging"
region      = "europe-west6"

# Staging domain
domain_name = "staging.compliance.ddys.ch"

# MongoDB Atlas
mongodb_atlas_org_id       = ""
mongodb_atlas_project_name = "ddys-compliance-staging"
mongodb_cluster_tier       = "M20"

# Moderate scaling
backend_cpu           = "1"
backend_memory        = "1Gi"
backend_min_instances = 1
backend_max_instances = 5
backend_concurrency   = 80

frontend_min_instances = 1
frontend_max_instances = 3

# Security enabled
cloud_armor_enabled  = true
rate_limit_threshold = 300

# Alerts
alert_email = "ops@ddys.ch"

# CI/CD
github_owner  = "DDYsGlobal"
github_repo   = "DDYsGlobal"
github_branch = "staging"

# Test tenants
initial_tenant_ids = ["test-bank"]

# Moderate retention
document_retention_days = 365

# Moderate budget
budget_amount = 300
