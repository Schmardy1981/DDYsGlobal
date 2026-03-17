###############################################################################
# Artifact Registry - Container Image Storage (Swiss Region)
###############################################################################

resource "google_artifact_registry_repository" "main" {
  location      = var.region
  repository_id = "ddys-${var.environment}"
  project       = var.project_id
  description   = "DDYs Compliance Platform container images (${var.environment})"
  format        = "DOCKER"

  cleanup_policies {
    id     = "keep-latest-10"
    action = "KEEP"

    most_recent_versions {
      keep_count = 10
    }
  }

  cleanup_policies {
    id     = "delete-old-untagged"
    action = "DELETE"

    condition {
      tag_state  = "UNTAGGED"
      older_than = "604800s" # 7 days
    }
  }

  labels = {
    environment = var.environment
    service     = "ddys-compliance"
  }

  depends_on = [google_project_service.apis["artifactregistry.googleapis.com"]]
}

# IAM: Cloud Build can push images
resource "google_artifact_registry_repository_iam_member" "build_writer" {
  location   = var.region
  repository = google_artifact_registry_repository.main.name
  project    = var.project_id
  role       = "roles/artifactregistry.writer"
  member     = "serviceAccount:${google_service_account.cloud_build.email}"
}

# IAM: Cloud Run can pull images
resource "google_artifact_registry_repository_iam_member" "run_reader" {
  location   = var.region
  repository = google_artifact_registry_repository.main.name
  project    = var.project_id
  role       = "roles/artifactregistry.reader"
  member     = "serviceAccount:${google_service_account.cloud_run.email}"
}
