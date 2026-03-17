###############################################################################
# Cloud Build - CI/CD Triggers
###############################################################################

# NOTE: Cloud Build GitHub connection must be set up manually via Console first:
# https://console.cloud.google.com/cloud-build/repositories
# After connecting, create triggers via Terraform.

# Backend build trigger
resource "google_cloudbuild_trigger" "backend" {
  count = var.github_owner != "" ? 1 : 0

  name        = "ddys-${var.environment}-backend-deploy"
  project     = var.project_id
  location    = var.region
  description = "Build and deploy DDYs backend on push to ${var.github_branch}"

  github {
    owner = var.github_owner
    name  = var.github_repo

    push {
      branch = "^${var.github_branch}$"
    }
  }

  included_files = ["backend/**", "Dockerfile.backend", "requirements.txt"]

  service_account = google_service_account.cloud_build.id

  substitutions = {
    _REGION      = var.region
    _ENVIRONMENT = var.environment
    _REPO_NAME   = "ddys-${var.environment}"
    _SERVICE     = "ddys-${var.environment}-backend"
  }

  filename = "cloudbuild.yaml"

  depends_on = [google_project_service.apis["cloudbuild.googleapis.com"]]
}

# Frontend build trigger
resource "google_cloudbuild_trigger" "frontend" {
  count = var.github_owner != "" ? 1 : 0

  name        = "ddys-${var.environment}-frontend-deploy"
  project     = var.project_id
  location    = var.region
  description = "Build and deploy DDYs frontend on push to ${var.github_branch}"

  github {
    owner = var.github_owner
    name  = var.github_repo

    push {
      branch = "^${var.github_branch}$"
    }
  }

  included_files = ["frontend/**", "Dockerfile.frontend", "nginx.conf"]

  service_account = google_service_account.cloud_build.id

  substitutions = {
    _REGION      = var.region
    _ENVIRONMENT = var.environment
    _REPO_NAME   = "ddys-${var.environment}"
    _SERVICE     = "ddys-${var.environment}-frontend"
  }

  filename = "cloudbuild-frontend.yaml"

  depends_on = [google_project_service.apis["cloudbuild.googleapis.com"]]
}
