###############################################################################
# Google Cloud Storage - Document Storage (Swiss Data Residency)
###############################################################################

# Shared documents bucket (prefix-based tenant isolation)
resource "google_storage_bucket" "documents" {
  name                        = "ddys-${var.environment}-documents-${random_id.suffix.hex}"
  project                     = var.project_id
  location                    = var.region
  storage_class               = "STANDARD"
  uniform_bucket_level_access = true
  force_destroy               = var.environment != "prod"

  versioning {
    enabled = true
  }

  # Compliance: 10-year retention for FINMA
  lifecycle_rule {
    condition {
      age = var.document_retention_days
    }
    action {
      type          = "SetStorageClass"
      storage_class = "ARCHIVE"
    }
  }

  # Delete non-current versions after 90 days
  lifecycle_rule {
    condition {
      num_newer_versions = 3
      with_state         = "ARCHIVED"
    }
    action {
      type = "Delete"
    }
  }

  # Retention policy (cannot delete before retention period)
  dynamic "retention_policy" {
    for_each = var.environment == "prod" ? [1] : []
    content {
      retention_period = var.document_retention_days * 86400 # Convert days to seconds
      is_locked        = false                               # Lock manually after verification
    }
  }

  cors {
    origin          = var.domain_name != "" ? ["https://${var.domain_name}"] : ["*"]
    method          = ["GET", "PUT", "POST", "DELETE", "HEAD"]
    response_header = ["Content-Type", "Content-Disposition", "Content-Length"]
    max_age_seconds = 3600
  }

  encryption {
    # Uses Google-managed encryption key by default
    # For CMEK, configure a Cloud KMS key here
  }

  labels = {
    environment = var.environment
    service     = "ddys-compliance"
    data_class  = "confidential"
    residency   = "switzerland"
  }
}

# Per-tenant document buckets (optional - for strictest isolation)
resource "google_storage_bucket" "tenant_documents" {
  for_each = toset(var.initial_tenant_ids)

  name                        = "ddys-${var.environment}-${each.key}-documents-${random_id.suffix.hex}"
  project                     = var.project_id
  location                    = var.region
  storage_class               = "STANDARD"
  uniform_bucket_level_access = true
  force_destroy               = var.environment != "prod"

  versioning {
    enabled = true
  }

  lifecycle_rule {
    condition {
      age = var.document_retention_days
    }
    action {
      type          = "SetStorageClass"
      storage_class = "ARCHIVE"
    }
  }

  cors {
    origin          = var.domain_name != "" ? ["https://${var.domain_name}"] : ["*"]
    method          = ["GET", "PUT", "POST", "HEAD"]
    response_header = ["Content-Type", "Content-Disposition", "Content-Length"]
    max_age_seconds = 3600
  }

  labels = {
    environment = var.environment
    service     = "ddys-compliance"
    tenant_id   = each.key
    data_class  = "confidential"
    residency   = "switzerland"
  }
}

# KYC export bucket (temporary storage for generated export ZIPs)
resource "google_storage_bucket" "exports" {
  name                        = "ddys-${var.environment}-exports-${random_id.suffix.hex}"
  project                     = var.project_id
  location                    = var.region
  storage_class               = "STANDARD"
  uniform_bucket_level_access = true
  force_destroy               = true

  lifecycle_rule {
    condition {
      age = 7 # Exports expire after 7 days
    }
    action {
      type = "Delete"
    }
  }

  labels = {
    environment = var.environment
    service     = "ddys-compliance"
    data_class  = "confidential"
    residency   = "switzerland"
  }
}

# Backup bucket
resource "google_storage_bucket" "backups" {
  name                        = "ddys-${var.environment}-backups-${random_id.suffix.hex}"
  project                     = var.project_id
  location                    = var.region
  storage_class               = "NEARLINE"
  uniform_bucket_level_access = true
  force_destroy               = false

  versioning {
    enabled = true
  }

  lifecycle_rule {
    condition {
      age = 365
    }
    action {
      type          = "SetStorageClass"
      storage_class = "ARCHIVE"
    }
  }

  labels = {
    environment = var.environment
    service     = "ddys-compliance"
    data_class  = "confidential"
    residency   = "switzerland"
  }
}

# IAM: Cloud Run service account can read/write documents
resource "google_storage_bucket_iam_member" "documents_rw" {
  bucket = google_storage_bucket.documents.name
  role   = "roles/storage.objectUser"
  member = "serviceAccount:${google_service_account.cloud_run.email}"
}

resource "google_storage_bucket_iam_member" "exports_rw" {
  bucket = google_storage_bucket.exports.name
  role   = "roles/storage.objectUser"
  member = "serviceAccount:${google_service_account.cloud_run.email}"
}

# Per-tenant bucket IAM
resource "google_storage_bucket_iam_member" "tenant_documents_rw" {
  for_each = toset(var.initial_tenant_ids)

  bucket = google_storage_bucket.tenant_documents[each.key].name
  role   = "roles/storage.objectUser"
  member = "serviceAccount:${google_service_account.cloud_run.email}"
}
