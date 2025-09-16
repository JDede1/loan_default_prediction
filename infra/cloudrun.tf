# ======================
# Artifact Registry Repo
# ======================
resource "google_artifact_registry_repository" "mlops" {
  location      = var.region
  repository_id = "mlops"
  description   = "Artifact Registry for MLflow + trainer images"
  format        = "DOCKER"
}

# ======================
# MLflow Service Account
# ======================
resource "google_service_account" "mlflow_sa" {
  account_id   = "mlflow-sa"
  display_name = "MLflow Service Account"
}

resource "google_project_iam_member" "mlflow_sa_storage" {
  project = var.project_id
  role    = "roles/storage.admin"
  member  = "serviceAccount:${google_service_account.mlflow_sa.email}"
}

resource "google_project_iam_member" "mlflow_sa_sql" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.mlflow_sa.email}"
}

# ======================
# MLflow Cloud Run
# ======================
resource "google_cloud_run_service" "mlflow" {
  name     = "mlflow"
  location = var.region

  template {
    spec {
      containers {
        image = "${var.region}-docker.pkg.dev/${var.project_id}/mlops/mlflow:latest"

        env {
          name  = "BACKEND_STORE_URI"
          value = "postgresql+psycopg2://mlflow:${random_password.mlflow.result}@/${google_sql_database.mlflow_db.name}?host=/cloudsql/${google_sql_database_instance.mlflow.connection_name}"
        }

        env {
          name  = "ARTIFACT_ROOT"
          value = "gs://${google_storage_bucket.artifacts.name}/mlflow"
        }
      }

      service_account_name = google_service_account.mlflow_sa.email
    }
  }

  autogenerate_revision_name = true
}

# Output endpoint
output "mlflow_url" {
  value = google_cloud_run_service.mlflow.status[0].url
}
