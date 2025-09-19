terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
  required_version = ">= 1.5.0"
}

provider "google" {
  project     = var.project_id
  region      = var.region
  credentials = file("${path.module}/../../keys/gcs-service-account.json")
}

# Enable required GCP APIs
resource "google_project_service" "storage_api" {
  project = var.project_id
  service = "storage.googleapis.com"
}

# GCS bucket for MLflow, predictions, reports, etc.
resource "google_storage_bucket" "artifacts" {
  name          = "loan-default-artifacts-loan-default-mlops"
  location      = "US-CENTRAL1"
  storage_class = "STANDARD"
  force_destroy = false

  uniform_bucket_level_access = true

  versioning {
    enabled = true
  }

  lifecycle_rule {
    action {
      type = "Delete"
    }
    condition {
      age = 30
    }
  }
}
