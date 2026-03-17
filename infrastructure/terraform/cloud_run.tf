###############################################################################
# Cloud Run - Backend (FastAPI)
###############################################################################

resource "google_cloud_run_v2_service" "backend" {
  name     = "ddys-${var.environment}-backend"
  location = var.region
  project  = var.project_id

  ingress = "INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER"

  template {
    service_account = google_service_account.cloud_run.email

    scaling {
      min_instance_count = var.backend_min_instances
      max_instance_count = var.backend_max_instances
    }

    max_instance_request_concurrency = var.backend_concurrency
    timeout                          = "${var.backend_timeout}s"

    vpc_access {
      connector = google_vpc_access_connector.serverless.id
      egress    = "PRIVATE_RANGES_ONLY"
    }

    containers {
      image = var.backend_image != "" ? var.backend_image : "${var.region}-docker.pkg.dev/${var.project_id}/ddys-${var.environment}/backend:latest"

      resources {
        limits = {
          cpu    = var.backend_cpu
          memory = var.backend_memory
        }
        cpu_idle          = var.environment == "prod" ? false : true
        startup_cpu_boost = true
      }

      ports {
        container_port = 8000
      }

      # Core environment variables
      env {
        name  = "ENVIRONMENT"
        value = var.environment == "prod" ? "production" : var.environment
      }
      env {
        name  = "GCP_PROJECT_ID"
        value = var.project_id
      }
      env {
        name  = "GCP_REGION"
        value = var.region
      }
      env {
        name  = "STORAGE_TYPE"
        value = "gcs"
      }
      env {
        name  = "FEATURE_S3_STORAGE"
        value = "false"
      }
      env {
        name  = "FEATURE_GCS_STORAGE"
        value = "true"
      }
      env {
        name  = "LOG_FORMAT"
        value = "json"
      }
      env {
        name  = "LOG_LEVEL"
        value = var.environment == "prod" ? "WARNING" : "INFO"
      }
      env {
        name  = "CORS_ORIGINS"
        value = var.domain_name != "" ? "https://${var.domain_name}" : "*"
      }
      env {
        name  = "RATE_LIMIT_DEFAULT"
        value = "100/minute"
      }
      env {
        name  = "RATE_LIMIT_AUTH"
        value = "10/minute"
      }
      env {
        name  = "RATE_LIMIT_UPLOAD"
        value = "20/minute"
      }
      env {
        name  = "GCS_BUCKET_PREFIX"
        value = "ddys-${var.environment}"
      }

      # Secrets from Secret Manager
      env {
        name = "JWT_SECRET"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.jwt_secret.secret_id
            version = "latest"
          }
        }
      }
      env {
        name = "MONGO_URL"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.mongo_url.secret_id
            version = "latest"
          }
        }
      }
      env {
        name  = "DB_NAME"
        value = "ddys_${var.environment}"
      }
      env {
        name = "EMERGENT_LLM_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.emergent_llm_key.secret_id
            version = "latest"
          }
        }
      }

      startup_probe {
        http_get {
          path = "/api/health"
          port = 8000
        }
        initial_delay_seconds = 5
        timeout_seconds       = 3
        period_seconds        = 5
        failure_threshold     = 10
      }

      liveness_probe {
        http_get {
          path = "/api/health"
          port = 8000
        }
        timeout_seconds   = 5
        period_seconds    = 30
        failure_threshold = 3
      }
    }
  }

  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }

  depends_on = [
    google_project_service.apis["run.googleapis.com"],
    google_secret_manager_secret_version.jwt_secret,
    google_secret_manager_secret_version.mongo_url,
    google_secret_manager_secret_version.emergent_llm_key,
  ]

  lifecycle {
    ignore_changes = [
      template[0].containers[0].image, # managed by CI/CD
    ]
  }
}

# Allow unauthenticated access (auth handled by app-level JWT)
# The LB + Cloud Armor handles WAF/rate-limiting at edge
resource "google_cloud_run_v2_service_iam_member" "backend_invoker" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.backend.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
