-- airflow/init-scripts/02_create_mlflow.sql
-- Ensures the mlflow database exists during Postgres initialization.
-- Runs only on first container startup with an empty data directory.

CREATE DATABASE mlflow OWNER airflow;
