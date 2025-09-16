# ======================
# Cloud SQL (Postgres)
# ======================

resource "google_sql_database_instance" "mlflow" {
  name             = "mlflow-postgres"
  database_version = "POSTGRES_14"
  region           = var.region

  settings {
    tier = "db-custom-1-3840" # small dev instance, adjust later
    availability_type = "REGIONAL"

    backup_configuration {
      enabled = true
    }

    ip_configuration {
      ipv4_enabled    = false
      private_network = google_compute_network.default.id
      require_ssl     = true
    }
  }

  deletion_protection = false
}

# Database for MLflow
resource "google_sql_database" "mlflow_db" {
  name     = "mlflow"
  instance = google_sql_database_instance.mlflow.name
}

# User for MLflow
resource "google_sql_user" "mlflow_user" {
  name     = "mlflow"
  instance = google_sql_database_instance.mlflow.name
  password = random_password.mlflow.result
}

# Random password for user
resource "random_password" "mlflow" {
  length  = 16
  special = true
}

# Outputs
output "mlflow_db_connection_name" {
  value = google_sql_database_instance.mlflow.connection_name
}

output "mlflow_db_password" {
  value     = random_password.mlflow.result
  sensitive = true
}
