###############################################################################
# Secret Manager - Secrets for DDYs Compliance Platform
###############################################################################

# --- Core Secrets ---

resource "google_secret_manager_secret" "jwt_secret" {
  secret_id = "ddys-${var.environment}-jwt-secret"
  project   = var.project_id

  replication {
    user_managed {
      replicas {
        location = var.region
      }
    }
  }

  labels = {
    environment = var.environment
    service     = "ddys-compliance"
  }

  depends_on = [google_project_service.apis["secretmanager.googleapis.com"]]
}

resource "google_secret_manager_secret_version" "jwt_secret" {
  secret      = google_secret_manager_secret.jwt_secret.id
  secret_data = "CHANGE_ME_AFTER_DEPLOY_${random_id.suffix.hex}"

  lifecycle {
    ignore_changes = [secret_data] # Don't overwrite after initial creation
  }
}

resource "google_secret_manager_secret" "mongo_url" {
  secret_id = "ddys-${var.environment}-mongo-url"
  project   = var.project_id

  replication {
    user_managed {
      replicas {
        location = var.region
      }
    }
  }

  labels = {
    environment = var.environment
    service     = "ddys-compliance"
  }

  depends_on = [google_project_service.apis["secretmanager.googleapis.com"]]
}

resource "google_secret_manager_secret_version" "mongo_url" {
  secret      = google_secret_manager_secret.mongo_url.id
  secret_data = "mongodb+srv://CHANGE_ME@cluster.mongodb.net/ddys_${var.environment}"

  lifecycle {
    ignore_changes = [secret_data]
  }
}

resource "google_secret_manager_secret" "emergent_llm_key" {
  secret_id = "ddys-${var.environment}-emergent-llm-key"
  project   = var.project_id

  replication {
    user_managed {
      replicas {
        location = var.region
      }
    }
  }

  labels = {
    environment = var.environment
    service     = "ddys-compliance"
  }

  depends_on = [google_project_service.apis["secretmanager.googleapis.com"]]
}

resource "google_secret_manager_secret_version" "emergent_llm_key" {
  secret      = google_secret_manager_secret.emergent_llm_key.id
  secret_data = "CHANGE_ME_AFTER_DEPLOY"

  lifecycle {
    ignore_changes = [secret_data]
  }
}

# --- IAM: Allow Cloud Run service account to access secrets ---

resource "google_secret_manager_secret_iam_member" "jwt_secret_access" {
  secret_id = google_secret_manager_secret.jwt_secret.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.cloud_run.email}"
}

resource "google_secret_manager_secret_iam_member" "mongo_url_access" {
  secret_id = google_secret_manager_secret.mongo_url.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.cloud_run.email}"
}

resource "google_secret_manager_secret_iam_member" "emergent_llm_key_access" {
  secret_id = google_secret_manager_secret.emergent_llm_key.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.cloud_run.email}"
}

# --- Cloud Build also needs secret access for integration tests ---

resource "google_secret_manager_secret_iam_member" "jwt_secret_build" {
  secret_id = google_secret_manager_secret.jwt_secret.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.cloud_build.email}"
}
