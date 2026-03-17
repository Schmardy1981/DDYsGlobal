###############################################################################
# DDYs Global Compliance Platform - GCP Infrastructure
# Region: europe-west6 (Zurich, Switzerland) - Swiss Data Residency
###############################################################################

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.30"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 5.30"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }

  backend "gcs" {
    # Configure via -backend-config or environment
    # bucket = "ddys-terraform-state-<project_id>"
    # prefix = "terraform/state"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

provider "google-beta" {
  project = var.project_id
  region  = var.region
}

# Enable required GCP APIs
resource "google_project_service" "apis" {
  for_each = toset([
    "run.googleapis.com",
    "compute.googleapis.com",
    "secretmanager.googleapis.com",
    "artifactregistry.googleapis.com",
    "cloudbuild.googleapis.com",
    "vpcaccess.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "iam.googleapis.com",
    "logging.googleapis.com",
    "monitoring.googleapis.com",
    "cloudtrace.googleapis.com",
    "certificatemanager.googleapis.com",
    "dns.googleapis.com",
    "servicenetworking.googleapis.com",
  ])

  project                    = var.project_id
  service                    = each.key
  disable_dependent_services = false
  disable_on_destroy         = false
}

# Random suffix for globally unique names
resource "random_id" "suffix" {
  byte_length = 4
}

# Terraform state bucket (create manually or via bootstrap script)
# gcloud storage buckets create gs://ddys-terraform-state-${PROJECT_ID} \
#   --location=europe-west6 --uniform-bucket-level-access
