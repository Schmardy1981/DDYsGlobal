# DDYs Global - Development Environment
project_id  = "ddys-compliance-dev"
environment = "dev"
region      = "europe-west6"

# No custom domain for dev
domain_name = ""

# MongoDB Atlas
mongodb_atlas_org_id       = ""
mongodb_atlas_project_name = "ddys-compliance-dev"
mongodb_cluster_tier       = "M10"

# Minimal scaling for dev
backend_cpu           = "1"
backend_memory        = "512Mi"
backend_min_instances = 0  # Scale to zero in dev
backend_max_instances = 3
backend_concurrency   = 40

frontend_min_instances = 0
frontend_max_instances = 2

# Security (relaxed for dev)
cloud_armor_enabled  = false
rate_limit_threshold = 1000

# No alerts in dev
alert_email = ""

# CI/CD
github_owner  = ""
github_repo   = "DDYsGlobal"
github_branch = "develop"

# No initial tenants (use seed endpoint)
initial_tenant_ids = []

# Shorter retention for dev
document_retention_days = 30

# Low budget
budget_amount = 100
