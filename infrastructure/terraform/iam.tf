###############################################################################
# IAM - Service Accounts & Permissions (Least Privilege)
###############################################################################

# --- Cloud Run Service Account ---
resource "google_service_account" "cloud_run" {
  account_id   = "ddys-${var.environment}-run-sa"
  display_name = "DDYs ${var.environment} Cloud Run Service Account"
  project      = var.project_id
}

# Cloud Run SA permissions
resource "google_project_iam_member" "cloud_run_roles" {
  for_each = toset([
    "roles/logging.logWriter",
    "roles/cloudtrace.agent",
    "roles/monitoring.metricWriter",
    "roles/errorreporting.writer",
  ])

  project = var.project_id
  role    = each.key
  member  = "serviceAccount:${google_service_account.cloud_run.email}"
}

# --- Cloud Build Service Account ---
resource "google_service_account" "cloud_build" {
  account_id   = "ddys-${var.environment}-build-sa"
  display_name = "DDYs ${var.environment} Cloud Build Service Account"
  project      = var.project_id
}

resource "google_project_iam_member" "cloud_build_roles" {
  for_each = toset([
    "roles/cloudbuild.builds.builder",
    "roles/run.developer",
    "roles/artifactregistry.writer",
    "roles/logging.logWriter",
    "roles/iam.serviceAccountUser",
  ])

  project = var.project_id
  role    = each.key
  member  = "serviceAccount:${google_service_account.cloud_build.email}"
}

# Cloud Build needs to act as Cloud Run SA during deploys
resource "google_service_account_iam_member" "build_acts_as_run" {
  service_account_id = google_service_account.cloud_run.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.cloud_build.email}"
}

# --- Workload Identity for CI/CD (GitHub Actions) ---
resource "google_iam_workload_identity_pool" "github" {
  count = var.github_owner != "" ? 1 : 0

  workload_identity_pool_id = "ddys-${var.environment}-github-pool"
  project                   = var.project_id
  display_name              = "GitHub Actions Pool"
  description               = "Workload Identity Pool for GitHub Actions CI/CD"
}

resource "google_iam_workload_identity_pool_provider" "github" {
  count = var.github_owner != "" ? 1 : 0

  workload_identity_pool_id          = google_iam_workload_identity_pool.github[0].workload_identity_pool_id
  workload_identity_pool_provider_id = "github-provider"
  project                            = var.project_id
  display_name                       = "GitHub Actions Provider"

  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.actor"      = "assertion.actor"
    "attribute.repository" = "assertion.repository"
  }

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }

  attribute_condition = "assertion.repository == '${var.github_owner}/${var.github_repo}'"
}

resource "google_service_account_iam_member" "github_workload_identity" {
  count = var.github_owner != "" ? 1 : 0

  service_account_id = google_service_account.cloud_build.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github[0].name}/attribute.repository/${var.github_owner}/${var.github_repo}"
}

# --- Org-level constraints to enforce Swiss data residency ---
# NOTE: These require Organization-level permissions. Apply separately if needed.
# resource "google_organization_policy" "gcp_resource_locations" {
#   org_id     = var.org_id
#   constraint = "constraints/gcp.resourceLocations"
#   list_policy {
#     allow {
#       values = ["in:europe-west6-locations"]
#     }
#   }
# }
