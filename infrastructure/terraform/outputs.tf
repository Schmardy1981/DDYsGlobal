###############################################################################
# Outputs
###############################################################################

# --- URLs ---
output "backend_url" {
  description = "Cloud Run backend URL"
  value       = google_cloud_run_v2_service.backend.uri
}

output "frontend_url" {
  description = "Cloud Run frontend URL"
  value       = google_cloud_run_v2_service.frontend.uri
}

output "load_balancer_ip" {
  description = "Global load balancer IP address"
  value       = google_compute_global_address.main.address
}

# --- Storage ---
output "documents_bucket" {
  description = "Main documents GCS bucket name"
  value       = google_storage_bucket.documents.name
}

output "exports_bucket" {
  description = "Exports GCS bucket name"
  value       = google_storage_bucket.exports.name
}

output "backups_bucket" {
  description = "Backups GCS bucket name"
  value       = google_storage_bucket.backups.name
}

output "tenant_buckets" {
  description = "Per-tenant document bucket names"
  value       = { for k, v in google_storage_bucket.tenant_documents : k => v.name }
}

# --- Registry ---
output "artifact_registry_url" {
  description = "Artifact Registry Docker URL"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.main.repository_id}"
}

# --- Service Accounts ---
output "cloud_run_service_account" {
  description = "Cloud Run service account email"
  value       = google_service_account.cloud_run.email
}

output "cloud_build_service_account" {
  description = "Cloud Build service account email"
  value       = google_service_account.cloud_build.email
}

# --- Network ---
output "vpc_network" {
  description = "VPC network name"
  value       = google_compute_network.main.name
}

output "vpc_connector" {
  description = "Serverless VPC connector name"
  value       = google_vpc_access_connector.serverless.name
}

# --- Secrets ---
output "secret_ids" {
  description = "Secret Manager secret IDs (for reference, not values)"
  value = {
    jwt_secret      = google_secret_manager_secret.jwt_secret.secret_id
    mongo_url       = google_secret_manager_secret.mongo_url.secret_id
    emergent_llm_key = google_secret_manager_secret.emergent_llm_key.secret_id
  }
}

# --- Workload Identity ---
output "workload_identity_provider" {
  description = "Workload Identity Provider for GitHub Actions"
  value       = var.github_owner != "" ? google_iam_workload_identity_pool_provider.github[0].name : "not configured"
}

# --- DNS Instructions ---
output "dns_instructions" {
  description = "DNS configuration required"
  value       = var.domain_name != "" ? "Create an A record for ${var.domain_name} pointing to ${google_compute_global_address.main.address}" : "No domain configured"
}
